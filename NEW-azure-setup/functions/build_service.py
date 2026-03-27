"""
Build Service for Azure Functions — extracts generated files to a temp
directory, runs Maven, streams output to Azure Table Storage for
real-time log display, and cleans up.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("build_service")

# ---------------------------------------------------------------------------
#  Azure Table Storage for real-time build logs
# ---------------------------------------------------------------------------

_table_client = None


async def _get_table_client():
    """Lazy-init the Azure Table Storage client for build logs."""
    global _table_client
    if _table_client is not None:
        return _table_client

    connection_string = os.getenv("AzureWebJobsStorage", "")
    if not connection_string or connection_string == "UseDevelopmentStorage=true":
        return None

    try:
        from azure.data.tables.aio import TableServiceClient

        service = TableServiceClient.from_connection_string(connection_string)
        _table_client = service.get_table_client("buildlogs")
        try:
            await _table_client.create_table()
        except Exception:
            pass  # table already exists
        return _table_client
    except Exception as exc:
        logger.warning("table_storage.init_failed: %s", exc)
        return None


async def _store_log_line(
    build_id: str,
    line_number: int,
    line: str,
    is_error: bool = False,
) -> None:
    """Write a single build log line to Azure Table Storage."""
    client = await _get_table_client()
    if client is None:
        return
    try:
        entity = {
            "PartitionKey": build_id,
            "RowKey": f"{line_number:08d}",
            "line": line[:32000],  # Table Storage limit
            "is_error": is_error,
            "timestamp_epoch": time.time(),
        }
        await client.upsert_entity(entity)
    except Exception as exc:
        logger.debug("table_storage.write_failed: %s", exc)


# ---------------------------------------------------------------------------
#  Default POM template (fallback when the engine doesn't generate one)
# ---------------------------------------------------------------------------

_DEFAULT_POM = """\
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                             https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.5</version>
        <relativePath/>
    </parent>
    <groupId>{group_id}</groupId>
    <artifactId>{artifact_id}</artifactId>
    <version>0.0.1-SNAPSHOT</version>
    <name>{project_name}</name>
    <description>Auto-generated Spring Boot project from MuleSoft migration</description>
    <properties>
        <java.version>{java_version}</java.version>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
"""


# ---------------------------------------------------------------------------
#  File extraction
# ---------------------------------------------------------------------------

def _extract_files(output_files: dict[str, str], target_dir: Path) -> int:
    """
    Write generated source files into the target directory.

    Sanitises paths to prevent directory-traversal attacks.
    Returns the number of files written.
    """
    count = 0
    for rel_path, content in output_files.items():
        safe_parts = Path(rel_path).parts
        if ".." in safe_parts:
            logger.warning("build.skipped_unsafe_path: %s", rel_path)
            continue
        full_path = target_dir / Path(*safe_parts)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        count += 1
    return count


def _ensure_pom(
    project_dir: Path,
    group_id: str,
    artifact_id: str,
    project_name: str,
    java_version: str,
) -> None:
    """Write a fallback pom.xml if none was generated."""
    pom_path = project_dir / "pom.xml"
    if not pom_path.exists():
        pom_path.write_text(
            _DEFAULT_POM.format(
                group_id=group_id,
                artifact_id=artifact_id,
                project_name=project_name,
                java_version=java_version,
            ),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
#  Maven execution
# ---------------------------------------------------------------------------

async def _run_maven(project_dir: Path, build_id: str) -> tuple[int, str]:
    """
    Run ``mvn clean package -DskipTests`` and stream output to
    Table Storage for real-time display.

    Returns (exit_code, full_build_log).
    """
    maven_cmd = shutil.which("mvn") or "mvn"
    cmd = [
        maven_cmd,
        "clean", "package",
        "-DskipTests",
        "-Dmaven.test.skip=true",
        "-Dmaven.compiler.failOnError=false",
        "-B",
        "--no-transfer-progress",
    ]

    log_lines: list[str] = []
    line_number = 0

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(project_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ, "JAVA_HOME": os.getenv("JAVA_HOME", "")},
        )

        for raw_line in iter(process.stdout.readline, ""):
            line = raw_line.rstrip("\n")
            log_lines.append(line)
            line_number += 1
            is_error = any(kw in line for kw in ["[ERROR]", "FAILURE", "BUILD FAILURE"])
            await _store_log_line(build_id, line_number, line, is_error)

        process.wait()
        exit_code = process.returncode

    except FileNotFoundError:
        msg = "Maven (mvn) not found on PATH. Please install Maven."
        log_lines.append(msg)
        await _store_log_line(build_id, line_number + 1, msg, True)
        exit_code = 127

    except Exception as exc:
        msg = f"Build process error: {exc}"
        log_lines.append(msg)
        await _store_log_line(build_id, line_number + 1, msg, True)
        exit_code = 1

    return exit_code, "\n".join(log_lines)


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

async def execute_build(
    build_id: str,
    migration_id: str,
    output_files: dict[str, str],
    project_name: str = "migrated-app",
    group_id: str = "com.example",
    java_version: str = "17",
) -> dict[str, Any]:
    """
    Full build pipeline: extract files, ensure pom, run Maven, clean up.

    Args:
        build_id:      UUID of the build job.
        migration_id:  UUID of the parent migration.
        output_files:  {relative_path: content} from the migration.
        project_name:  Project display name.
        group_id:      Maven group ID.
        java_version:  Target Java version.

    Returns:
        Dict with status, exit_code, duration_ms, build_log.
    """
    artifact_id = project_name.lower().replace(" ", "-")
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"build_{build_id[:8]}_"))

    try:
        file_count = _extract_files(output_files, tmp_dir)
        logger.info("build.files_extracted: count=%d dir=%s", file_count, tmp_dir)

        _ensure_pom(tmp_dir, group_id, artifact_id, project_name, java_version)

        start = time.monotonic()
        exit_code, full_log = await _run_maven(tmp_dir, build_id)
        duration_ms = int((time.monotonic() - start) * 1000)

        status = "completed" if exit_code == 0 else "failed"

        logger.info(
            "build.finished: id=%s exit=%d duration=%dms",
            build_id, exit_code, duration_ms,
        )

        return {
            "status": status,
            "build_id": build_id,
            "migration_id": migration_id,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "build_log": full_log[-50_000:],  # truncate to ~50 KB
        }

    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception as exc:
            logger.warning("build.cleanup_failed: %s", exc)
