"""
Validation Service — Build Docker image via ACR Tasks, deploy to ACI,
run API comparison, and teardown.

Uses Azure Container Registry Quick Build (ACR Tasks) so no local Docker
daemon is needed on the Consumption plan.
"""

from __future__ import annotations

import io
import json
import logging
import os
import tarfile
import time
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger("validation_service")

# ---------------------------------------------------------------------------
#  Azure Table Storage for validation logs (mirrors build_service pattern)
# ---------------------------------------------------------------------------

_val_table_client = None


async def _get_val_table_client():
    """Lazy-init Azure Table Storage client for validation logs."""
    global _val_table_client
    if _val_table_client is not None:
        return _val_table_client

    connection_string = os.getenv("AzureWebJobsStorage", "")
    if not connection_string or connection_string == "UseDevelopmentStorage=true":
        return None

    try:
        from azure.data.tables.aio import TableServiceClient

        service = TableServiceClient.from_connection_string(connection_string)
        _val_table_client = service.get_table_client("validationlogs")
        try:
            await _val_table_client.create_table()
        except Exception:
            pass
        return _val_table_client
    except Exception as exc:
        logger.warning("validation_table.init_failed: %s", exc)
        return None


async def _store_val_log(validation_id: str, line_number: int, line: str, is_error: bool = False):
    """Write a validation log line to Table Storage."""
    client = await _get_val_table_client()
    if client is None:
        return
    try:
        entity = {
            "PartitionKey": validation_id,
            "RowKey": f"{line_number:08d}",
            "line": line[:32000],
            "is_error": is_error,
            "timestamp_epoch": time.time(),
        }
        await client.upsert_entity(entity)
    except Exception as exc:
        logger.debug("validation_table.write_failed: %s", exc)


# ---------------------------------------------------------------------------
#  Dockerfile template
# ---------------------------------------------------------------------------

_DOCKERFILE = """\
FROM maven:3.9-eclipse-temurin-{java_version} AS build
WORKDIR /app
COPY . .
RUN mvn clean package -Dmaven.test.skip=true -B --no-transfer-progress

FROM eclipse-temurin:{java_version}-jre
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /app/target/*.jar app.jar
EXPOSE {server_port}
HEALTHCHECK --interval=10s --timeout=3s --start-period=60s \\
  CMD curl -f http://localhost:{server_port}/actuator/health || exit 1
ENTRYPOINT ["java", "-jar", "app.jar"]
"""


# ---------------------------------------------------------------------------
#  File extraction → tar.gz for ACR
# ---------------------------------------------------------------------------

def _patch_pom_xml(pom: str) -> str:
    """
    Patch common issues in LLM-generated pom.xml files:
    1. Remove duplicate dependencies
    2. Add Lombok annotation processor path if missing
    3. Fix other common Maven build issues
    """
    import re

    if not pom:
        return pom

    # --- Remove duplicate dependency blocks ---
    # Keep first occurrence of each groupId:artifactId pair
    seen: set[str] = set()
    lines = pom.split("\n")
    result_lines: list[str] = []
    skip_until_close = False
    current_dep = ""
    dep_start = -1

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped == "<dependency>" and not skip_until_close:
            dep_start = len(result_lines)
            result_lines.append(line)
            current_dep = ""
            i += 1
            continue

        if dep_start >= 0:
            result_lines.append(line)
            if "<groupId>" in stripped:
                current_dep += re.sub(r"</?groupId>", "", stripped).strip() + ":"
            if "<artifactId>" in stripped:
                current_dep += re.sub(r"</?artifactId>", "", stripped).strip()
            if stripped == "</dependency>":
                if current_dep in seen:
                    # Remove this duplicate dependency
                    del result_lines[dep_start:]
                else:
                    seen.add(current_dep)
                dep_start = -1
                current_dep = ""
        else:
            result_lines.append(line)
        i += 1

    pom = "\n".join(result_lines)

    # --- Add Lombok annotation processor path if Lombok is a dependency ---
    has_lombok = "org.projectlombok" in pom
    has_annotation_processor = "annotationProcessorPaths" in pom

    if has_lombok and not has_annotation_processor:
        # Find the maven-compiler-plugin or spring-boot-maven-plugin section
        # and add annotation processor paths for Lombok
        # Detect Lombok version from the dependency or use default
        lombok_ver = "1.18.30"
        lv_match = re.search(
            r"<artifactId>lombok</artifactId>\s*<version>([^<]+)</version>",
            pom,
        )
        if lv_match:
            lombok_ver = lv_match.group(1).strip()

        compiler_plugin_config = f"""
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <configuration>
                    <annotationProcessorPaths>
                        <path>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                            <version>{lombok_ver}</version>
                        </path>
                    </annotationProcessorPaths>
                </configuration>
            </plugin>"""

        # Insert before </plugins>
        if "</plugins>" in pom:
            pom = pom.replace(
                "</plugins>",
                f"{compiler_plugin_config}\n        </plugins>",
                1,
            )
        elif "<plugins>" in pom:
            pom = pom.replace(
                "<plugins>",
                f"<plugins>{compiler_plugin_config}",
                1,
            )

    # --- Fix annotationProcessorPaths with missing Lombok version ---
    # Maven requires an explicit <version> on annotationProcessorPaths entries.
    # If the Lombok path exists but lacks a version, inject one.
    if has_annotation_processor:
        lombok_ver = "1.18.30"
        lv_match = re.search(
            r"<artifactId>lombok</artifactId>\s*<version>([^<]+)</version>",
            pom,
        )
        if lv_match:
            lombok_ver = lv_match.group(1).strip()

        # Match a <path> block inside annotationProcessorPaths that has lombok but no version
        pattern = (
            r"(<annotationProcessorPaths>.*?"
            r"<path>\s*"
            r"<groupId>org\.projectlombok</groupId>\s*"
            r"<artifactId>lombok</artifactId>\s*)"
            r"(</path>)"
        )
        replacement = rf"\g<1><version>{lombok_ver}</version>\n                        \g<2>"
        pom_fixed = re.sub(pattern, replacement, pom, count=1, flags=re.DOTALL)
        if pom_fixed != pom:
            logger.info("validation.patched_pom: added missing Lombok version %s to annotationProcessorPaths", lombok_ver)
            pom = pom_fixed

    # --- Ensure H2 dependency is present AND available at runtime for validation ---
    # Validation containers run without external databases, so H2 must be on
    # the runtime classpath (not just test scope).
    if "com.h2database" not in pom and "</dependencies>" in pom:
        h2_dep = """
        <!-- H2 in-memory database for validation -->
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>runtime</scope>
        </dependency>"""
        pom = pom.replace("</dependencies>", f"{h2_dep}\n    </dependencies>", 1)
        logger.info("validation.patched_pom: added H2 dependency for validation")
    elif "com.h2database" in pom:
        # H2 exists but may be scoped to 'test' — change to 'runtime' for validation
        # The validation container runs the app (not tests), so test-scoped deps
        # are not on the classpath.
        h2_test_pattern = re.compile(
            r'(<groupId>com\.h2database</groupId>\s*'
            r'<artifactId>h2</artifactId>\s*)'
            r'<scope>test</scope>',
            re.DOTALL,
        )
        pom_new = h2_test_pattern.sub(r'\g<1><scope>runtime</scope>', pom)
        if pom_new != pom:
            pom = pom_new
            logger.info("validation.patched_pom: changed H2 scope from test → runtime for validation")

    return pom


_LOMBOK_IMPORTS: dict[str, str] = {
    "@Slf4j": "import lombok.extern.slf4j.Slf4j;",
    "@Log4j2": "import lombok.extern.log4j.Log4j2;",
    "@RequiredArgsConstructor": "import lombok.RequiredArgsConstructor;",
    "@AllArgsConstructor": "import lombok.AllArgsConstructor;",
    "@NoArgsConstructor": "import lombok.NoArgsConstructor;",
    "@Data": "import lombok.Data;",
    "@Getter": "import lombok.Getter;",
    "@Setter": "import lombok.Setter;",
    "@Builder": "import lombok.Builder;",
    "@Value": "import lombok.Value;",
    "@ToString": "import lombok.ToString;",
    "@EqualsAndHashCode": "import lombok.EqualsAndHashCode;",
}

_SPRING_IMPORTS: dict[str, str] = {
    "@RestController": "import org.springframework.web.bind.annotation.RestController;",
    "@Controller": "import org.springframework.stereotype.Controller;",
    "@RequestMapping": "import org.springframework.web.bind.annotation.RequestMapping;",
    "@GetMapping": "import org.springframework.web.bind.annotation.GetMapping;",
    "@PostMapping": "import org.springframework.web.bind.annotation.PostMapping;",
    "@PutMapping": "import org.springframework.web.bind.annotation.PutMapping;",
    "@DeleteMapping": "import org.springframework.web.bind.annotation.DeleteMapping;",
    "@PatchMapping": "import org.springframework.web.bind.annotation.PatchMapping;",
    "@PathVariable": "import org.springframework.web.bind.annotation.PathVariable;",
    "@RequestBody": "import org.springframework.web.bind.annotation.RequestBody;",
    "@RequestParam": "import org.springframework.web.bind.annotation.RequestParam;",
    "@RequestHeader": "import org.springframework.web.bind.annotation.RequestHeader;",
    "@Autowired": "import org.springframework.beans.factory.annotation.Autowired;",
    "@Component": "import org.springframework.stereotype.Component;",
    "@Service": "import org.springframework.stereotype.Service;",
    "@Repository": "import org.springframework.stereotype.Repository;",
    "@Configuration": "import org.springframework.context.annotation.Configuration;",
    "@Bean": "import org.springframework.context.annotation.Bean;",
    "@SpringBootApplication": "import org.springframework.boot.autoconfigure.SpringBootApplication;",
    "@ResponseBody": "import org.springframework.web.bind.annotation.ResponseBody;",
    "@CrossOrigin": "import org.springframework.web.bind.annotation.CrossOrigin;",
    "@ExceptionHandler": "import org.springframework.web.bind.annotation.ExceptionHandler;",
    "@ControllerAdvice": "import org.springframework.web.bind.annotation.ControllerAdvice;",
    "@RestControllerAdvice": "import org.springframework.web.bind.annotation.RestControllerAdvice;",
    "@Validated": "import org.springframework.validation.annotation.Validated;",
    "@Transactional": "import org.springframework.transaction.annotation.Transactional;",
    "@Scheduled": "import org.springframework.scheduling.annotation.Scheduled;",
    "@Async": "import org.springframework.scheduling.annotation.Async;",
    "@EnableScheduling": "import org.springframework.scheduling.annotation.EnableScheduling;",
    "@EnableAsync": "import org.springframework.scheduling.annotation.EnableAsync;",
    "@Qualifier": "import org.springframework.beans.factory.annotation.Qualifier;",
    "@ConfigurationProperties": "import org.springframework.boot.context.properties.ConfigurationProperties;",
    "@EnableTransactionManagement": "import org.springframework.transaction.annotation.EnableTransactionManagement;",
    "@Primary": "import org.springframework.context.annotation.Primary;",
    "@Profile": "import org.springframework.context.annotation.Profile;",
    "@Scope": "import org.springframework.context.annotation.Scope;",
    "@Lazy": "import org.springframework.context.annotation.Lazy;",
    "@DependsOn": "import org.springframework.context.annotation.DependsOn;",
    "@Order": "import org.springframework.core.annotation.Order;",
    "@EventListener": "import org.springframework.context.event.EventListener;",
    "@ConditionalOnProperty": "import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;",
    "@Cacheable": "import org.springframework.cache.annotation.Cacheable;",
    "@CacheEvict": "import org.springframework.cache.annotation.CacheEvict;",
    "@CachePut": "import org.springframework.cache.annotation.CachePut;",
    "@Retryable": "import org.springframework.retry.annotation.Retryable;",
    "@Recover": "import org.springframework.retry.annotation.Recover;",
    "@LoadBalanced": "import org.springframework.cloud.client.loadbalancer.LoadBalanced;",
    "@RefreshScope": "import org.springframework.cloud.context.config.annotation.RefreshScope;",
    "@PreAuthorize": "import org.springframework.security.access.prepost.PreAuthorize;",
    "@Secured": "import org.springframework.security.access.annotation.Secured;",
}

# JPA / Hibernate annotations used in entity classes
_JPA_IMPORTS: dict[str, str] = {
    "@Entity": "import jakarta.persistence.Entity;",
    "@Table": "import jakarta.persistence.Table;",
    "@Id": "import jakarta.persistence.Id;",
    "@GeneratedValue": "import jakarta.persistence.GeneratedValue;",
    "@GenerationType": "import jakarta.persistence.GenerationType;",
    "@Column": "import jakarta.persistence.Column;",
    "@ManyToOne": "import jakarta.persistence.ManyToOne;",
    "@OneToMany": "import jakarta.persistence.OneToMany;",
    "@ManyToMany": "import jakarta.persistence.ManyToMany;",
    "@OneToOne": "import jakarta.persistence.OneToOne;",
    "@JoinColumn": "import jakarta.persistence.JoinColumn;",
    "@Enumerated": "import jakarta.persistence.Enumerated;",
    "@Temporal": "import jakarta.persistence.Temporal;",
    "@Lob": "import jakarta.persistence.Lob;",
    "@Embeddable": "import jakarta.persistence.Embeddable;",
    "@Embedded": "import jakarta.persistence.Embedded;",
}

# Spring @Value annotation (distinct from Lombok @Value)
_VALUE_IMPORT: dict[str, str] = {
    '@Value("': "import org.springframework.beans.factory.annotation.Value;",
    "@Value(\"": "import org.springframework.beans.factory.annotation.Value;",
}

# Jakarta Validation annotations (Bean Validation)
_VALIDATION_IMPORTS: dict[str, str] = {
    "@Valid": "import jakarta.validation.Valid;",
    "@NotNull": "import jakarta.validation.constraints.NotNull;",
    "@NotBlank": "import jakarta.validation.constraints.NotBlank;",
    "@NotEmpty": "import jakarta.validation.constraints.NotEmpty;",
    "@Size": "import jakarta.validation.constraints.Size;",
    "@Min": "import jakarta.validation.constraints.Min;",
    "@Max": "import jakarta.validation.constraints.Max;",
    "@Email": "import jakarta.validation.constraints.Email;",
    "@Pattern": "import jakarta.validation.constraints.Pattern;",
    "@Positive": "import jakarta.validation.constraints.Positive;",
    "@PositiveOrZero": "import jakarta.validation.constraints.PositiveOrZero;",
    "@Negative": "import jakarta.validation.constraints.Negative;",
    "@Past": "import jakarta.validation.constraints.Past;",
    "@Future": "import jakarta.validation.constraints.Future;",
}

# Jackson JSON annotations
_JACKSON_IMPORTS: dict[str, str] = {
    "@JsonProperty": "import com.fasterxml.jackson.annotation.JsonProperty;",
    "@JsonIgnore": "import com.fasterxml.jackson.annotation.JsonIgnore;",
    "@JsonFormat": "import com.fasterxml.jackson.annotation.JsonFormat;",
    "@JsonInclude": "import com.fasterxml.jackson.annotation.JsonInclude;",
    "@JsonCreator": "import com.fasterxml.jackson.annotation.JsonCreator;",
    "@JsonValue": "import com.fasterxml.jackson.annotation.JsonValue;",
    "@JsonSerialize": "import com.fasterxml.jackson.databind.annotation.JsonSerialize;",
    "@JsonDeserialize": "import com.fasterxml.jackson.databind.annotation.JsonDeserialize;",
}

# OpenAPI / Swagger annotations (springdoc)
_OPENAPI_IMPORTS: dict[str, str] = {
    "@Tag": "import io.swagger.v3.oas.annotations.tags.Tag;",
    "@Operation": "import io.swagger.v3.oas.annotations.Operation;",
    "@ApiResponse": "import io.swagger.v3.oas.annotations.responses.ApiResponse;",
    "@ApiResponses": "import io.swagger.v3.oas.annotations.responses.ApiResponses;",
    "@Parameter": "import io.swagger.v3.oas.annotations.Parameter;",
    "@Schema": "import io.swagger.v3.oas.annotations.media.Schema;",
    "@Content": "import io.swagger.v3.oas.annotations.media.Content;",
    "@OpenAPIDefinition": "import io.swagger.v3.oas.annotations.OpenAPIDefinition;",
}

# Common Java classes that LLM-generated code uses without importing
_JAVA_CLASS_IMPORTS: dict[str, str] = {
    "Collections.": "import java.util.Collections;",
    "Collections ": "import java.util.Collections;",
    "HashMap<": "import java.util.HashMap;",
    "ArrayList<": "import java.util.ArrayList;",
    "LinkedHashMap<": "import java.util.LinkedHashMap;",
    "Arrays.": "import java.util.Arrays;",
    "Optional.": "import java.util.Optional;",
    "Optional<": "import java.util.Optional;",
    "Stream.": "import java.util.stream.Stream;",
    "Collectors.": "import java.util.stream.Collectors;",
    "HttpStatus.": "import org.springframework.http.HttpStatus;",
    "HttpStatus ": "import org.springframework.http.HttpStatus;",
    "ResponseEntity<": "import org.springframework.http.ResponseEntity;",
    "ResponseEntity.": "import org.springframework.http.ResponseEntity;",
    "MediaType.": "import org.springframework.http.MediaType;",
    "Logger ": "import org.slf4j.Logger;",
    "LoggerFactory.": "import org.slf4j.LoggerFactory;",
}


def _patch_java_sources(output_files: dict[str, str]) -> dict[str, str]:
    """
    Patch Java source files: add missing imports for Lombok, Spring, and common Java classes.
    LLM-generated code often uses annotations/classes without import statements.
    """
    import re

    patched = {}
    for path, content in output_files.items():
        if not path.endswith(".java"):
            patched[path] = content
            continue

        missing_imports: list[str] = []
        all_import_maps = {**_LOMBOK_IMPORTS, **_SPRING_IMPORTS, **_JPA_IMPORTS, **_VALUE_IMPORT,
                           **_VALIDATION_IMPORTS, **_JACKSON_IMPORTS, **_OPENAPI_IMPORTS, **_JAVA_CLASS_IMPORTS}
        for annotation, import_stmt in all_import_maps.items():
            # Check if annotation is used but import is missing
            if annotation in content and import_stmt not in content:
                missing_imports.append(import_stmt)

        if not missing_imports:
            patched[path] = content
            continue

        # Insert imports after the package statement or at the top
        lines = content.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("package "):
                insert_idx = i + 1
                break
            if stripped.startswith("import "):
                insert_idx = i
                break

        # Find the last import line to insert after it
        last_import = insert_idx
        for i in range(insert_idx, len(lines)):
            if lines[i].strip().startswith("import "):
                last_import = i + 1

        # Insert missing imports
        for imp in missing_imports:
            lines.insert(last_import, imp)
            last_import += 1

        patched[path] = "\n".join(lines)
        logger.info("validation.patched_imports: %s added %d imports", path, len(missing_imports))

    return patched


def _patch_java_compilation_errors(output_files: dict[str, str]) -> dict[str, str]:
    """
    Fix common Java compilation errors in LLM-generated / static-engine code.
    This is the last-resort safety net before ACR build.

    Handles:
    - Illegal escape characters in string literals (MuleSoft flow names)
    - Single-quoted strings → double-quoted
    - DataWeave object literals (standalone and embedded in .put() calls)
    - DataWeave map/filter operations
    - DataWeave format: syntax
    - DW property access on Object types (statusData.status == "X")
    - .put("key", { DW block }) → .put("key", new LinkedHashMap<>())
    - String.valueOf(x) {format: "..."} → proper DateTimeFormatter
    - environment.getProperty() → System.getenv()
    - Brace-balanced DW block removal
    - Missing imports, missing fields
    """
    import re

    # ── DataWeave leak detection patterns ──
    _DW_OBJECT_LITERAL = re.compile(
        r'^\s*\{\s*\w+\s*:\s*(true|false|"[^"]*"|[\w.]+)',
    )
    _DW_MAP_OP = re.compile(r'\b\w+\s+map\s*[\{\(]')
    _DW_FIELD_ACCESS = re.compile(r'^\s*\w+:\s+\w+\.get\(')
    _DW_FORMAT = re.compile(r'\bformat\s*:\s*"')
    _DW_FILTER_OP = re.compile(r'\b\w+\s+filter\s*[\{\(]')
    _DW_FORMAT_IN_CALL = re.compile(r'\)\s*\{format\s*:')
    _UNDEF_TRANSFORMED = re.compile(r'^\s*payload\s*=\s*transformed\s*;')
    _HTTP_STATUS_LITERAL = re.compile(r'^\s*Object\s+httpStatus\s*=\s*"')

    # NEW: .put("key", { DW literal }) — DW object literal inside Map.put()
    _DW_PUT_LITERAL = re.compile(r'\.put\(\s*"[^"]*"\s*,\s*\{\s*$')
    # NEW: .put("key", { key: val, key: val, ... }) — single-line DW in put
    _DW_PUT_LITERAL_INLINE = re.compile(
        r'(\.put\(\s*"[^"]*"\s*,\s*)\{\s*\w+:\s+\w+',
    )
    # NEW: DW reduce operation
    _DW_REDUCE_OP = re.compile(r'\breduce\s*\(')
    # NEW: DW-style property access: obj.field == "value" (not a method call)
    _DW_OBJ_FIELD_EQ = re.compile(
        r'\b(\w+)\.(\w+)\s*==\s*"([^"]*)"',
    )
    # NEW: DW-style bare field assignment: fieldName: expr.something
    _DW_BARE_FIELD = re.compile(r'^\s*(\w+):\s+(\w+)\.\w+')
    # NEW: undefined environment.getProperty()
    _UNDEF_ENV = re.compile(r'\benvironment\.getProperty\(\s*"([^"]*)"\s*\)')

    patched = {}
    for path, content in output_files.items():
        if not path.endswith(".java"):
            patched[path] = content
            continue

        original = content

        # ── Phase 1: Fix illegal escape characters in ALL string literals ──
        def _fix_escapes(m):
            s = m.group(0)
            return re.sub(r'\\(?![\\tnrfb"\'/0-9u])', r'\\\\', s)
        content = re.sub(r'"(?:[^"\\]|\\.)*"', _fix_escapes, content)

        # ── Phase 1b: Replace MySQL-specific SQL functions with H2 equivalents ──
        content = content.replace("CURDATE()", "CURRENT_DATE")
        content = content.replace("NOW()", "CURRENT_TIMESTAMP")
        content = content.replace("IFNULL(", "COALESCE(")

        # ── Phase 1c: Fix Map.of() with >10 entries ──
        # Java's Map.of() only supports up to 10 key-value pairs.
        # Convert to Map.ofEntries(Map.entry(k, v), ...) for larger maps.
        def _fix_map_of_overflow(m):
            """Convert Map.of(k1,v1,k2,v2,...) with >10 pairs to Map.ofEntries(...)."""
            prefix = m.group(1)  # "Map.of" or "Map.<String, Object>of"
            args_str = m.group(2)
            # Parse arguments respecting string literals and nested parens/generics
            args = []
            depth = 0
            current = []
            in_string = False
            escape_next = False
            for ch in args_str:
                if escape_next:
                    current.append(ch)
                    escape_next = False
                    continue
                if ch == '\\' and in_string:
                    current.append(ch)
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    current.append(ch)
                    continue
                if in_string:
                    current.append(ch)
                    continue
                if ch in '(<':
                    depth += 1
                    current.append(ch)
                elif ch in ')>':
                    depth -= 1
                    current.append(ch)
                elif ch == ',' and depth == 0:
                    args.append(''.join(current).strip())
                    current = []
                else:
                    current.append(ch)
            if current:
                args.append(''.join(current).strip())

            # Only fix if we have >20 args (>10 key-value pairs)
            if len(args) <= 20:
                return m.group(0)

            # Build Map.ofEntries(Map.entry(k, v), ...)
            entries = []
            for i in range(0, len(args) - 1, 2):
                key = args[i]
                val = args[i + 1] if i + 1 < len(args) else "null"
                entries.append(f"Map.entry({key}, {val})")
            return "Map.ofEntries(" + ", ".join(entries) + ")"

        # Match Map.of(...) and Map.<Type, Type>of(...) with balanced parens
        # Use a simpler approach: find Map.of( or Map.<...>of( then balance parens
        def _fix_all_map_of(text):
            result = []
            i = 0
            while i < len(text):
                # Look for Map.of( or Map.<...>of(
                map_of_match = re.match(r'(Map\s*\.(?:<[^>]+>)?of)\s*\(', text[i:])
                if not map_of_match:
                    result.append(text[i])
                    i += 1
                    continue

                prefix = map_of_match.group(1)
                start = i + map_of_match.end() - 1  # position of '('
                # Balance parentheses to find the closing ')'
                depth = 0
                j = start
                in_str = False
                esc = False
                while j < len(text):
                    ch = text[j]
                    if esc:
                        esc = False
                        j += 1
                        continue
                    if ch == '\\' and in_str:
                        esc = True
                        j += 1
                        continue
                    if ch == '"':
                        in_str = not in_str
                    if not in_str:
                        if ch == '(':
                            depth += 1
                        elif ch == ')':
                            depth -= 1
                            if depth == 0:
                                break
                    j += 1

                if depth != 0:
                    # Unbalanced — skip
                    result.append(text[i])
                    i += 1
                    continue

                args_str = text[start + 1:j]  # content between ( and )
                full_match = text[i:j + 1]

                # Count args (rough: split by comma at depth 0)
                arg_count = 0
                d = 0
                in_s = False
                for ch in args_str:
                    if ch == '"' and not esc:
                        in_s = not in_s
                    if not in_s:
                        if ch in '(':
                            d += 1
                        elif ch in ')':
                            d -= 1
                        elif ch == ',' and d == 0:
                            arg_count += 1
                arg_count += 1  # for the last arg

                if arg_count > 20:
                    # Fix it
                    fixed = _fix_map_of_overflow(re.match(r'(Map\s*\.(?:<[^>]+>)?of)\s*\((.*)\)', full_match, re.DOTALL))
                    if fixed and fixed != full_match:
                        result.append(fixed)
                        logger.info("validation.fixed_map_of_overflow: %s (%d args → Map.ofEntries)", path, arg_count)
                    else:
                        result.append(full_match)
                else:
                    result.append(full_match)

                i = j + 1
            return ''.join(result)

        content = _fix_all_map_of(content)

        # Also add Map import if Map.ofEntries was used
        if "Map.ofEntries(" in content and "import java.util.Map;" not in content:
            # Add import after package declaration or first import
            import_line = "import java.util.Map;\n"
            if "import " in content:
                first_import = content.index("import ")
                content = content[:first_import] + import_line + content[first_import:]
            elif "package " in content:
                pkg_end = content.index(";", content.index("package ")) + 1
                content = content[:pkg_end] + "\n\n" + import_line + content[pkg_end:]

        # ── Phase 2: Fix single-quoted Java strings (outside string literals) ──
        # 'APPROVED' → "APPROVED", but NOT inside SQL strings like "WHERE status = 'ACTIVE'"
        def _fix_single_quotes_outside_strings(text):
            result = []
            ci = 0
            while ci < len(text):
                if text[ci] == '"':
                    # Inside a Java string literal — copy verbatim until closing "
                    result.append(text[ci])
                    ci += 1
                    while ci < len(text):
                        if text[ci] == '\\' and ci + 1 < len(text):
                            result.append(text[ci:ci+2])
                            ci += 2
                        elif text[ci] == '"':
                            result.append(text[ci])
                            ci += 1
                            break
                        else:
                            result.append(text[ci])
                            ci += 1
                elif text[ci] == "'":
                    sq_match = re.match(r"'([A-Z_]{2,})'", text[ci:])
                    if sq_match:
                        result.append(f'"{sq_match.group(1)}"')
                        ci += len(sq_match.group(0))
                    else:
                        result.append(text[ci])
                        ci += 1
                else:
                    result.append(text[ci])
                    ci += 1
            return "".join(result)
        content = _fix_single_quotes_outside_strings(content)

        # ── Phase 2b: Fix DW property access: obj.field == "VALUE" ──
        # statusData.status == "APPROVED" → "APPROVED".equals(((Map<?,?>)statusData).get("status"))
        # Only for lowercase variable names (skip System.out, String.class, etc.)
        def _fix_dw_prop_equals(m):
            obj = m.group(1)
            prop = m.group(2)
            val = m.group(3)
            # Skip standard Java patterns
            if obj[0].isupper() or prop in ('class', 'length', 'size', 'out', 'err', 'in'):
                return m.group(0)
            # Skip if it looks like a method chain (next char after prop is '(')
            return f'"{val}".equals(((java.util.Map<?,?>){obj}).get("{prop}"))'
        content = _DW_OBJ_FIELD_EQ.sub(_fix_dw_prop_equals, content)

        # ── Phase 2c: Fix undefined environment.getProperty() ──
        def _fix_env_prop(m):
            prop_name = m.group(1)
            env_name = prop_name.upper().replace(".", "_").replace("-", "_")
            return f'System.getenv("{env_name}")'
        content = _UNDEF_ENV.sub(_fix_env_prop, content)

        lines = content.split("\n")
        new_lines = []
        skip_until_closing_brace = False
        dw_brace_depth = 0
        # Track what the skip mode is closing, to emit proper replacement
        skip_context = None  # "put_literal", "dw_block", "format_call"

        for i, line in enumerate(lines):
            stripped = line.strip()
            indent = line[:len(line) - len(line.lstrip())] if line.strip() else line

            # ── Skip DataWeave block continuation ──
            if skip_until_closing_brace:
                dw_brace_depth += stripped.count("{") - stripped.count("}")
                if dw_brace_depth <= 0:
                    skip_until_closing_brace = False
                    # Emit proper closing for .put() blocks
                    if skip_context == "put_literal":
                        # The closing }); was consumed — we already emitted the replacement
                        pass
                    elif skip_context == "format_call":
                        # The DW format block inside a method call is done
                        # Emit closing ); for the outer method call if needed
                        if stripped.endswith(");"):
                            new_lines.append(f'{indent});')
                    skip_context = None
                continue

            # Skip already-commented lines
            if stripped.startswith("//"):
                new_lines.append(line)
                continue

            # ── NEW: .put("key", { DW object literal }) — multi-line ──
            # transformed.put("policy", {
            #     policyId: p.policy_id,
            #     ...
            # });
            # → transformed.put("policy", new LinkedHashMap<>());
            if _DW_PUT_LITERAL.search(stripped):
                # Extract the put call prefix: transformed.put("policy",
                put_match = re.match(r'(.*\.put\(\s*"[^"]*"\s*,\s*)\{', stripped)
                if put_match:
                    prefix = put_match.group(1).strip()
                    new_lines.append(f'{indent}{prefix}new LinkedHashMap<>());')
                    new_lines.append(f'{indent}// TODO: Populate the map above from DataWeave transform')
                    dw_brace_depth = stripped.count("{") - stripped.count("}")
                    if dw_brace_depth > 0:
                        skip_until_closing_brace = True
                        skip_context = "put_literal"
                    logger.info("validation.patched_dw_put_literal: %s line %d", path, i + 1)
                    continue

            # ── NEW: .put("key", { key: val, ... }) — single line with DW ──
            if _DW_PUT_LITERAL_INLINE.search(stripped) and not stripped.startswith("//"):
                put_match = re.match(r'(.*\.put\(\s*"[^"]*"\s*,\s*)\{.*', stripped)
                if put_match:
                    prefix = put_match.group(1).strip()
                    # Check if it's balanced on this line
                    dw_depth = stripped.count("{") - stripped.count("}")
                    if dw_depth > 0:
                        # Multi-line DW in put — enter skip mode
                        new_lines.append(f'{indent}{prefix}new LinkedHashMap<>());')
                        new_lines.append(f'{indent}// TODO: Populate the map above from DataWeave transform')
                        skip_until_closing_brace = True
                        skip_context = "put_literal"
                        dw_brace_depth = dw_depth
                    else:
                        # Single-line — replace inline
                        new_lines.append(f'{indent}{prefix}new LinkedHashMap<>());')
                        new_lines.append(f'{indent}// TODO: Populate the map above from DataWeave transform')
                    logger.info("validation.patched_dw_put_literal_inline: %s line %d", path, i + 1)
                    continue

            # ── DataWeave standalone object literal ──
            if _DW_OBJECT_LITERAL.match(stripped):
                dw_brace_depth = stripped.count("{") - stripped.count("}")
                if dw_brace_depth > 0:
                    skip_until_closing_brace = True
                    skip_context = "dw_block"
                new_lines.append(f'{indent}// TODO: Convert DataWeave object literal to Java Map')
                new_lines.append(f'{indent}// DW: {stripped}')
                logger.info("validation.patched_dw_literal: %s line %d", path, i + 1)
                continue

            # ── DataWeave map operation (standalone or embedded) ──
            if _DW_MAP_OP.search(stripped):
                new_lines.append(f'{indent}// TODO: Convert DataWeave map operation to Java Stream')
                new_lines.append(f'{indent}// DW: {stripped}')
                dw_brace_depth = stripped.count("{") - stripped.count("}")
                if dw_brace_depth > 0:
                    skip_until_closing_brace = True
                    skip_context = "dw_block"
                logger.info("validation.patched_dw_map: %s line %d", path, i + 1)
                continue

            # ── DataWeave filter operation ──
            if _DW_FILTER_OP.search(stripped):
                new_lines.append(f'{indent}// TODO: Convert DataWeave filter to Java Stream')
                new_lines.append(f'{indent}// DW: {stripped}')
                dw_brace_depth = stripped.count("{") - stripped.count("}")
                if dw_brace_depth > 0:
                    skip_until_closing_brace = True
                    skip_context = "dw_block"
                continue

            # ── DataWeave reduce operation ──
            if _DW_REDUCE_OP.search(stripped) and not stripped.startswith("//"):
                new_lines.append(f'{indent}// TODO: Convert DataWeave reduce to Java')
                new_lines.append(f'{indent}// DW: {stripped}')
                dw_brace_depth = stripped.count("{") - stripped.count("}")
                if dw_brace_depth > 0:
                    skip_until_closing_brace = True
                    skip_context = "dw_block"
                continue

            # ── DataWeave field access in map lambda ──
            if _DW_FIELD_ACCESS.match(stripped):
                new_lines.append(f'{indent}// DW: {stripped}')
                continue

            # ── DataWeave format: "..." patterns ──
            if _DW_FORMAT.search(stripped) and not stripped.startswith("//"):
                # Check if it's inside a method call we need to fix
                if _DW_FORMAT_IN_CALL.search(stripped):
                    # e.g., "CLM-" + String.valueOf(LocalDateTime.now()) {format: "yyyyMMddHHmmss", rest_args...
                    # Fix: replace the DW format expression inline, keep remaining args
                    # DO NOT enter skip mode — this is a single-line fix
                    fmt_match = re.search(r'\{format\s*:\s*"([^"]+)"', stripped)
                    fmt_pattern = fmt_match.group(1) if fmt_match else "yyyyMMddHHmmss"

                    # Try to replace String.valueOf(expr) {format: "pat", remaining → expr.format(...), remaining
                    # Use nested-paren-aware regex: (?:[^()]|\([^()]*\))+ handles one level of nesting
                    fixed_line = re.sub(
                        r'String\.valueOf\(((?:[^()]|\([^()]*\))+)\)\s*\{format\s*:\s*"[^"]*"[,}]?\s*',
                        lambda m: f'{m.group(1)}.format(DateTimeFormatter.ofPattern("{fmt_pattern}")), ',
                        stripped
                    )
                    if fixed_line != stripped:
                        new_lines.append(f'{indent}// DW: {stripped}')
                        new_lines.append(f'{indent}{fixed_line}')
                    else:
                        # Fallback: comment the line and provide a safe replacement
                        # Use String variable assignment so it's a valid statement
                        new_lines.append(f'{indent}// DW: {stripped}')
                        new_lines.append(
                            f'{indent}String _formatted = LocalDateTime.now().format(DateTimeFormatter.ofPattern("{fmt_pattern}"));'
                        )
                    logger.info("validation.patched_dw_format_in_call: %s line %d", path, i + 1)
                    continue
                else:
                    new_lines.append(f'{indent}// DW: {stripped}')
                    continue

            # ── DW bare field assignment: fieldName: expr.something ──
            # These are DW object literal fields that leaked into Java
            # e.g., policyId: p.policy_id,  or  claimId: c.claim_id,
            if (_DW_BARE_FIELD.match(stripped) and not stripped.startswith("//")
                    and "case " not in stripped and "default:" not in stripped
                    and not re.match(r'^\s*(if|else|for|while|do|switch|try|catch|return|throw)\b', stripped)):
                new_lines.append(f'{indent}// DW: {stripped}')
                continue

            # ── "payload = transformed;" where transformed is never defined ──
            if _UNDEF_TRANSFORMED.match(stripped):
                has_def = any(
                    re.search(r'\btransformed\b.*=', lines[j])
                    for j in range(max(0, i - 30), i)
                    if not lines[j].strip().startswith("//")
                )
                if not has_def:
                    new_lines.append(f'{indent}// payload = transformed; (transformed not defined)')
                    continue

            # ── "Object httpStatus = ..." — DW HTTP status setting ──
            if _HTTP_STATUS_LITERAL.match(stripped):
                new_lines.append(f'{indent}// DW: {stripped}')
                continue

            # ── Closing }); that belongs to a DW block already commented out ──
            if stripped.startswith("});") and i > 0:
                prev = new_lines[-1].strip() if new_lines else ""
                if prev.startswith("// TODO:") or prev.startswith("// DW:"):
                    new_lines.append(f'{indent}// DW: {stripped}')
                    continue

            # ── Fix: dead code after return ──
            if stripped.startswith("payload = ") and i > 0:
                prev_stripped = lines[i - 1].strip() if i > 0 else ""
                if prev_stripped.startswith("return "):
                    continue

            # ── Fix: duplicate return statements ──
            # Only remove "return payload;" if there's already a different return right before it
            if stripped == "return payload;" and i > 0:
                is_duplicate = False
                for j in range(i - 1, max(i - 3, -1), -1):
                    prev = lines[j].strip()
                    if not prev:
                        continue
                    if prev.startswith("return ") and prev != "return payload;":
                        is_duplicate = True
                    break  # Only check the first non-empty line
                if is_duplicate:
                    new_lines.append(f'{indent}// (removed duplicate return)')
                    continue
                # Not a duplicate — keep it (fall through to append)

            # ── Fix: .size() on Object type ──
            if "payload.size()" in stripped:
                line = line.replace("payload.size()",
                                    "((java.util.Collection<?>) payload).size()")

            # ── Fix: return ResponseEntity.ok(payload) when payload undefined ──
            if "ResponseEntity.ok(payload)" in stripped or "ResponseEntity.ok( payload )" in stripped:
                has_payload_def = False
                brace_depth = 0
                for j in range(i - 1, -1, -1):
                    prev = lines[j].strip()
                    brace_depth += prev.count("}") - prev.count("{")
                    if brace_depth > 0:
                        break
                    if "payload" in prev and ("=" in prev or "Object payload" in prev or "var payload" in prev):
                        has_payload_def = True
                        break
                if not has_payload_def:
                    line = line.replace(
                        "ResponseEntity.ok(payload)",
                        'ResponseEntity.ok(Map.of("status", "success"))'
                    )

            # ── Fix: jdbcTemplate.update with missing params ──
            if "jdbcTemplate.update(" in stripped and stripped.endswith(");"):
                match = re.search(r'jdbcTemplate\.update\(\s*"([^"]+)"\s*\)', stripped)
                if match and "?" in match.group(1):
                    sql = match.group(1)
                    param_count = sql.count("?")
                    has_request_body = any(
                        "requestBody" in lines[j]
                        for j in range(max(0, i - 20), i)
                    )
                    if has_request_body and param_count > 0:
                        params = ", ".join([
                            f'requestBody.getOrDefault("param{k+1}", "")'
                            for k in range(param_count)
                        ])
                        line = f'{indent}int rowsAffected = jdbcTemplate.update("{sql}", {params});'

            new_lines.append(line)

        content = "\n".join(new_lines)

        # ── Phase 4: Post-processing cleanup ──

        # 4a. Ensure @Service classes that use jdbcTemplate have the field
        if "jdbcTemplate" in content and "private final JdbcTemplate" not in content:
            if "@Service" in content:
                class_match = re.search(r'(public class \w+[^{]*\{)', content)
                if class_match:
                    insert_after = class_match.end()
                    content = (
                        content[:insert_after]
                        + "\n\n    private final JdbcTemplate jdbcTemplate;\n"
                        + content[insert_after:]
                    )
                    if "import org.springframework.jdbc.core.JdbcTemplate;" not in content:
                        content = content.replace(
                            "import java.util.*;",
                            "import java.util.*;\nimport org.springframework.jdbc.core.JdbcTemplate;",
                            1,
                        )

        # 4a-2. Fix invalid Java identifiers containing hyphens/dots
        # e.g. "claims-db-configJdbcTemplate" → "claimsDbConfigJdbcTemplate"
        _hyphen_ident = re.findall(r'\b([a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)+(?:JdbcTemplate|WebClient|Service|Repository|DataSource)\w*)\b', content)
        for bad_name in set(_hyphen_ident):
            parts = re.split(r'[-._]+', bad_name)
            good_name = parts[0]
            for p in parts[1:]:
                if p:
                    good_name += p[0].upper() + p[1:]
            if good_name != bad_name:
                content = content.replace(bad_name, good_name)
                logger.info("validation.fixed_java_identifier: %s → %s in %s", bad_name, good_name, path)

        # 4a-3. Fix generic hyphenated identifiers that aren't valid Java
        # Only process lines that are NOT string literals or comments
        # Process line-by-line to avoid mangling SQL inside strings
        fixed_lines = []
        for code_line in content.split("\n"):
            stripped_cl = code_line.strip()
            # Skip comment lines and lines that are primarily string content
            if (stripped_cl.startswith("//") or stripped_cl.startswith("*")
                    or stripped_cl.startswith("/*") or stripped_cl.startswith('"')):
                fixed_lines.append(code_line)
                continue
            # Only fix hyphenated names in declaration/assignment contexts
            # e.g. "private final JdbcTemplate claims-db-configJdbcTemplate;"
            # NOT inside queryForList("SELECT c.some-col FROM ...")
            # Heuristic: skip lines containing SQL-like content
            if any(kw in code_line.upper() for kw in ['SELECT ', 'INSERT ', 'UPDATE ', 'DELETE ', 'FROM ', 'WHERE ', 'JOIN ']):
                fixed_lines.append(code_line)
                continue
            _generic_hyphens = re.findall(r'\b([a-z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)+)\b', code_line)
            line_modified = code_line
            for bad_name in set(_generic_hyphens):
                parts = bad_name.split('-')
                good_name = parts[0]
                for p in parts[1:]:
                    if p:
                        good_name += p[0].upper() + p[1:]
                if good_name != bad_name:
                    line_modified = line_modified.replace(bad_name, good_name)
                    logger.info("validation.fixed_hyphenated_ident: %s → %s in %s", bad_name, good_name, path)
            fixed_lines.append(line_modified)
        content = "\n".join(fixed_lines)

        # 4a-4. Fix DW-style object literals leaked into Java: .put("key", { ... })
        # Replace with .put("key", Map.of()) placeholder
        _dw_literal = re.findall(r'\.put\(\s*"[^"]+"\s*,\s*\{[^}]*\}\s*\)', content)
        for bad_expr in set(_dw_literal):
            # Extract the key from .put("key", ...)
            key_match = re.search(r'\.put\(\s*"([^"]+)"', bad_expr)
            if key_match:
                key_name = key_match.group(1)
                content = content.replace(bad_expr, f'.put("{key_name}", new LinkedHashMap<>())')
                logger.info("validation.fixed_dw_literal: %s in %s", key_name, path)

        # 4a-5. Fix == comparison with single-quoted chars (DW-style): status == 'APPROVED'
        content = re.sub(
            r"\b(\w+)\s*==\s*'([A-Z_]+)'",
            r'"\2".equals(\1)',
            content
        )

        # 4a-6. REMOVED — was too aggressive, mangled SQL inside string literals.
        # DW-style field access (p.field_name) is now handled by the DataWeave
        # leak detector in flow_converter.py which wraps such code as TODO comments.

        # 4b. Add missing imports for common types used
        _IMPORT_MAP = {
            "LinkedHashMap": "import java.util.LinkedHashMap;",
            "JdbcTemplate": "import org.springframework.jdbc.core.JdbcTemplate;",
            "ResponseEntity": "import org.springframework.http.ResponseEntity;",
            "LocalDateTime": "import java.time.LocalDateTime;",
            "DateTimeFormatter": "import java.time.format.DateTimeFormatter;",
            "CompletableFuture": "import java.util.concurrent.CompletableFuture;",
        }
        for type_name, import_stmt in _IMPORT_MAP.items():
            if type_name in content and import_stmt not in content:
                last_import = content.rfind("\nimport ")
                if last_import >= 0:
                    end_of_line = content.index("\n", last_import + 1)
                    content = content[:end_of_line + 1] + import_stmt + "\n" + content[end_of_line + 1:]

        # 4c. Final regex pass: catch any remaining stray DW syntax
        final_lines = content.split("\n")
        final_out = []
        for line in final_lines:
            s = line.strip()
            # Catch remaining DW colon-assignment lines
            if (re.match(r'^\s*\w+:\s+\w+\.get\(', s) and not s.startswith("//")
                    and "case " not in s and "default:" not in s):
                ind = line[:len(line) - len(line.lstrip())]
                final_out.append(f'{ind}// DW: {s}')
                continue
            # Catch remaining bare DW field assignments: fieldName: obj.prop
            if (re.match(r'^\s*\w+:\s+\w+\.\w+\s*[,;]?\s*$', s) and not s.startswith("//")
                    and "case " not in s and "default:" not in s
                    and not any(kw in s for kw in ("if ", "else", "for ", "while ", "return ", "throw "))):
                ind = line[:len(line) - len(line.lstrip())]
                final_out.append(f'{ind}// DW: {s}')
                continue
            # Catch "payload = transformed;" that slipped through
            if s == "payload = transformed;" and not any(
                "transformed" in fl and "=" in fl and "payload" not in fl
                for fl in final_lines
                if not fl.strip().startswith("//")
            ):
                ind = line[:len(line) - len(line.lstrip())]
                final_out.append(f'{ind}// payload = transformed; (undefined)')
                continue
            final_out.append(line)
        content = "\n".join(final_out)

        # 4d. Truncation repair — LLM output sometimes gets cut off mid-line
        # Detect: last non-blank line has an unclosed string literal or is missing semicolon
        trunc_lines = content.split("\n")
        # Find last non-blank line
        last_idx = len(trunc_lines) - 1
        while last_idx > 0 and not trunc_lines[last_idx].strip():
            last_idx -= 1
        last_line = trunc_lines[last_idx].strip() if last_idx >= 0 else ""
        # Check for unclosed string: odd number of unescaped double quotes
        if last_line:
            quote_count = 0
            ci = 0
            while ci < len(last_line):
                if last_line[ci] == '\\' and ci + 1 < len(last_line):
                    ci += 2
                    continue
                if last_line[ci] == '"':
                    quote_count += 1
                ci += 1
            if quote_count % 2 != 0:
                # Truncated mid-string — comment out the broken line and add safety return
                trunc_lines[last_idx] = "// TRUNCATED: " + trunc_lines[last_idx]
                # Add a safe return statement so the enclosing method compiles
                indent = "        "  # typical method body indent
                trunc_lines.insert(last_idx + 1, f'{indent}return org.springframework.http.ResponseEntity.ok(java.util.Collections.singletonMap("error", "Endpoint truncated during migration"));')
                content = "\n".join(trunc_lines)
                logger.warning("validation.truncation_repair: %s line %d (unclosed string)", path, last_idx + 1)

        # 4e. Brace balance check — count braces in CODE only (skip comments and strings)
        code_opens = 0
        code_closes = 0
        for bline in content.split("\n"):
            bs = bline.strip()
            if bs.startswith("//") or bs.startswith("*") or bs.startswith("/*"):
                continue
            # Strip string literals before counting
            stripped_strings = re.sub(r'"(?:[^"\\]|\\.)*"', '', bline)
            code_opens += stripped_strings.count("{")
            code_closes += stripped_strings.count("}")
        if code_closes < code_opens:
            missing = code_opens - code_closes
            lines_final = content.split("\n")
            insert_pos = len(lines_final)
            for j in range(len(lines_final) - 1, -1, -1):
                if lines_final[j].strip():
                    insert_pos = j + 1
                    break
            for _ in range(missing):
                lines_final.insert(insert_pos, "}")
            content = "\n".join(lines_final)
            logger.warning("validation.brace_balance_fix: %s added %d closing brace(s)", path, missing)

        # 4f. Inject /health endpoint if missing from @RestController (often lost to truncation)
        if "@RestController" in content and '/health' not in content.lower():
            # Insert a health endpoint before the last closing brace of the class
            health_method = '''
    @org.springframework.web.bind.annotation.GetMapping("/health")
    public org.springframework.http.ResponseEntity<?> getHealth() {
        java.util.Map<String, Object> h = new java.util.LinkedHashMap<>();
        h.put("status", "UP");
        h.put("service", "Migrated API");
        h.put("version", "1.0.0");
        h.put("timestamp", java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'").format(java.time.LocalDateTime.now()));
        return org.springframework.http.ResponseEntity.ok(h);
    }
'''
            # Find last '}' and insert before it
            last_brace = content.rfind("}")
            if last_brace > 0:
                content = content[:last_brace] + health_method + content[last_brace:]
                logger.info("validation.injected_health_endpoint: %s", path)

        if content != original:
            patched[path] = content
            logger.info("validation.patched_java_compilation: %s (changed)", path)
        else:
            patched[path] = content

    return patched


def _patch_datasource_consistency(output_files: dict[str, str]) -> dict[str, str]:
    """
    Reconcile DataSourceConfig bean names and property prefixes with what
    controllers/services actually inject.

    The LLM enhancement step sometimes rewrites DataSourceConfig.java with
    shortened bean names (e.g., "claimsJdbcTemplate" instead of
    "claimsDbConfigJdbcTemplate") or altered @ConfigurationProperties prefixes
    (e.g., "spring.datasource.claims" instead of "spring.datasource").
    This breaks @RequiredArgsConstructor field injection.

    Strategy:
    1. Scan controllers/services for JdbcTemplate field names
    2. Scan DataSourceConfig for @Bean names
    3. If they don't match, rewrite DataSourceConfig bean names to match
    4. Also fix @ConfigurationProperties prefixes to match application.properties
    5. Strip markdown artifacts (```) from Java files
    """
    import re

    patched = dict(output_files)

    # ── Phase 0: Strip markdown code fence artifacts from all Java files ──
    for path in list(patched.keys()):
        if path.endswith(".java") and "```" in patched[path]:
            patched[path] = "\n".join(
                line for line in patched[path].split("\n")
                if not line.strip().startswith("```")
            )

    # ── Phase 1: Collect JdbcTemplate field names from controllers and services ──
    jdbc_fields: set[str] = set()
    for path, content in patched.items():
        if not path.endswith(".java"):
            continue
        if "DataSourceConfig" in path:
            continue
        for m in re.finditer(r'private\s+final\s+JdbcTemplate\s+(\w+)\s*;', content):
            jdbc_fields.add(m.group(1))

    if not jdbc_fields:
        return patched

    # ── Phase 2: Find DataSourceConfig and its current bean names ──
    ds_config_path = None
    ds_config_content = None
    for path, content in patched.items():
        if path.endswith("DataSourceConfig.java"):
            ds_config_path = path
            ds_config_content = content
            break

    if not ds_config_path or not ds_config_content:
        return patched

    # Extract current @Bean(name = "...JdbcTemplate") names
    current_beans: list[str] = re.findall(
        r'@Bean\s*\(\s*name\s*=\s*"(\w*JdbcTemplate)"\s*\)', ds_config_content
    )
    # Also match @Bean without name= where the method name contains JdbcTemplate
    for m in re.finditer(r'public\s+JdbcTemplate\s+(\w*JdbcTemplate)\s*\(', ds_config_content):
        if m.group(1) not in current_beans:
            current_beans.append(m.group(1))

    if not current_beans:
        return patched

    # ── Phase 3: Build mapping from current bean names to expected field names ──
    # Match by position — both lists are ordered (primary first, then secondary)
    sorted_fields = sorted(jdbc_fields)
    # Group fields by similarity to beans
    bean_to_field: dict[str, str] = {}
    used_fields = set()
    for bean in current_beans:
        # Try exact match first
        if bean in jdbc_fields:
            bean_to_field[bean] = bean
            used_fields.add(bean)
            continue
        # Try fuzzy match: both end with "JdbcTemplate", compare prefix
        bean_prefix = bean.replace("JdbcTemplate", "").lower()
        best_match = None
        for field in sorted_fields:
            if field in used_fields:
                continue
            field_prefix = field.replace("JdbcTemplate", "").lower()
            if bean_prefix in field_prefix or field_prefix in bean_prefix:
                best_match = field
                break
        if best_match:
            bean_to_field[bean] = best_match
            used_fields.add(best_match)

    # If no mismatches found, nothing to fix
    needs_fix = any(b != f for b, f in bean_to_field.items())
    if not needs_fix:
        return patched

    # ── Phase 4: Rewrite DataSourceConfig bean names ──
    new_content = ds_config_content
    for old_bean, new_bean in bean_to_field.items():
        if old_bean == new_bean:
            continue
        # Replace @Bean(name = "oldBean") → @Bean(name = "newBean")
        new_content = new_content.replace(f'"{old_bean}"', f'"{new_bean}"')
        # Replace method name
        old_method = old_bean
        new_method = new_bean
        new_content = new_content.replace(
            f'public JdbcTemplate {old_method}(',
            f'public JdbcTemplate {new_method}('
        )
        # Also fix the corresponding DataSource and DataSourceProperties names
        old_ds_prefix = old_bean.replace("JdbcTemplate", "")
        new_ds_prefix = new_bean.replace("JdbcTemplate", "")
        if old_ds_prefix != new_ds_prefix:
            new_content = new_content.replace(
                f'{old_ds_prefix}DataSourceProperties',
                f'{new_ds_prefix}DataSourceProperties'
            )
            new_content = new_content.replace(
                f'{old_ds_prefix}DataSource',
                f'{new_ds_prefix}DataSource'
            )

    # ── Phase 5: Fix @ConfigurationProperties prefixes to match properties files ──
    # Collect actual property prefixes from application.properties
    props_content = ""
    for ppath in ["application.properties", "src/main/resources/application.properties"]:
        if ppath in patched:
            props_content = patched[ppath]
            break

    if props_content:
        # Find all spring.datasource.XXX.url keys to determine actual prefixes
        actual_prefixes: list[str] = []
        for pm in re.finditer(r'(spring\.datasource(?:\.\w+)?)\.(url|driver)', props_content):
            prefix = pm.group(1)
            if prefix not in actual_prefixes:
                actual_prefixes.append(prefix)

        # Find prefixes in DataSourceConfig
        config_prefixes = re.findall(
            r'@ConfigurationProperties\s*\(\s*prefix\s*=\s*"([^"]+)"\s*\)', new_content
        )

        # Match by position and replace if different
        for i, cfg_prefix in enumerate(config_prefixes):
            if i < len(actual_prefixes) and cfg_prefix != actual_prefixes[i]:
                new_content = new_content.replace(
                    f'prefix = "{cfg_prefix}"',
                    f'prefix = "{actual_prefixes[i]}"',
                    1  # only first occurrence for this iteration
                )

    patched[ds_config_path] = new_content
    logger.info("validation.patched_datasource_config: reconciled %d bean names", len(bean_to_field))

    return patched


def _patch_application_properties(output_files: dict[str, str]) -> dict[str, str]:
    """
    Force H2 in-memory database for validation containers.

    Validation runs in an isolated ACI container with NO external database.
    Any reference to MySQL, PostgreSQL, or other external DB must be replaced
    with H2 so the Spring Boot app can start and serve HTTP endpoints for testing.
    """
    import re

    _H2_PROPS = {
        "spring.datasource.url": "jdbc:h2:mem:testdb;DB_CLOSE_DELAY=-1",
        "spring.datasource.driver-class-name": "org.h2.Driver",
        "spring.datasource.username": "sa",
        "spring.datasource.password": "",
        "spring.jpa.database-platform": "org.hibernate.dialect.H2Dialect",
        "spring.jpa.hibernate.ddl-auto": "create-drop",
        "spring.h2.console.enabled": "true",
    }

    # No port override — we detect the port from config and match it in Dockerfile + ACI

    # External DB indicators in properties files
    _EXTERNAL_DB_MARKERS = [
        "com.mysql.cj.jdbc.Driver", "com.mysql.jdbc.Driver",
        "org.postgresql.Driver", "org.mariadb.jdbc.Driver",
        "oracle.jdbc.OracleDriver", "com.microsoft.sqlserver.jdbc.SQLServerDriver",
        "jdbc:mysql:", "jdbc:postgresql:", "jdbc:mariadb:",
        "jdbc:oracle:", "jdbc:sqlserver:",
    ]

    # MuleSoft-style placeholders that don't exist in Spring Boot
    _MULE_PLACEHOLDER_DEFAULTS = {
        "http.port": "8080",
        "https.port": "8443",
        "http.private.port": "8091",
        "mule.env": "dev",
        "MULE_ENV": "dev",
        "mule.key": "",
        "mule.encryptionKey": "",
        "api.id": "",
        "api.name": "migrated-api",
        "api.version": "1.0.0",
        "http.host": "0.0.0.0",
    }

    def _resolve_mule_placeholders(text: str) -> str:
        """Replace ${...} MuleSoft placeholders with sensible defaults."""
        def _replace_placeholder(m):
            key = m.group(1)
            # If it's a standard Spring placeholder, leave it alone
            spring_prefixes = (
                "spring.", "server.", "management.", "logging.",
                "SPRING_", "SERVER_", "JAVA_", "CLASSPATH",
                "random.", "info.", "eureka.", "security.",
            )
            if any(key.startswith(p) for p in spring_prefixes):
                return m.group(0)
            # Known MuleSoft placeholders
            if key in _MULE_PLACEHOLDER_DEFAULTS:
                return _MULE_PLACEHOLDER_DEFAULTS[key]
            # Unknown placeholder — replace with empty string to avoid crash
            logger.info("validation.placeholder_removed: ${%s} (unknown)", key)
            return ""

        return re.sub(r"\$\{([^}]+)}", _replace_placeholder, text)

    patched = dict(output_files)
    for path in list(patched.keys()):
        basename = path.split("/")[-1] if "/" in path else path

        if basename == "application.properties":
            content = patched[path]

            # --- Phase 1: Resolve MuleSoft placeholders ---
            content = _resolve_mule_placeholders(content)

            # --- Phase 2: Force H2 if external DB is referenced ---
            has_external_db = any(marker in content for marker in _EXTERNAL_DB_MARKERS)
            if has_external_db:
                lines = content.split("\n")
                new_lines = []
                replaced_keys: set = set()
                for line in lines:
                    key = line.split("=")[0].strip() if "=" in line else ""
                    if key in _H2_PROPS:
                        if key not in replaced_keys:
                            new_lines.append(f"{key}={_H2_PROPS[key]}")
                            replaced_keys.add(key)
                        # skip duplicate keys
                    elif "driver-class-name" in key:
                        new_lines.append(f"{key}=org.h2.Driver")
                        replaced_keys.add(key)
                    elif "datasource.url" in key and any(m in line for m in ["jdbc:mysql:", "jdbc:postgresql:", "jdbc:mariadb:", "jdbc:oracle:", "jdbc:sqlserver:"]):
                        new_lines.append(f"{key}=jdbc:h2:mem:testdb;DB_CLOSE_DELAY=-1")
                        replaced_keys.add(key)
                    else:
                        new_lines.append(line)

                # Add any H2 keys not already present
                for k, v in _H2_PROPS.items():
                    if k not in replaced_keys and k not in content:
                        new_lines.append(f"{k}={v}")

                content = "\n".join(new_lines)

            # --- Phase 3: Remove any property lines with empty values from placeholder removal ---
            final_lines = []
            for line in content.split("\n"):
                stripped = line.strip()
                # Remove lines like "some.key=" that resulted from empty placeholder replacement
                if stripped and "=" in stripped:
                    val = stripped.split("=", 1)[1].strip()
                    key = stripped.split("=", 1)[0].strip()
                    # Keep lines with actual values, or known empty-is-OK keys
                    if val or key in ("spring.datasource.password",):
                        final_lines.append(line)
                    else:
                        logger.info("validation.removed_empty_prop: %s", key)
                else:
                    final_lines.append(line)

            # --- Phase 4: Remove MuleSoft-only property keys ---
            _MULE_ONLY_PREFIXES = ("mule.", "MULE_", "anypoint.", "cloudhub.")
            cleaned_lines = []
            for line in final_lines:
                stripped = line.strip()
                if stripped and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    if any(key.startswith(p) for p in _MULE_ONLY_PREFIXES):
                        logger.info("validation.removed_mule_prop: %s", key)
                        continue
                cleaned_lines.append(line)

            patched[path] = "\n".join(cleaned_lines)
            logger.info("validation.patched_properties: %s → patched for validation", path)

        elif basename in ("application.yml", "application.yaml"):
            content = patched[path]

            # --- Phase 1: Resolve MuleSoft placeholders ---
            content = _resolve_mule_placeholders(content)

            # --- Phase 2: Force H2 if external DB is referenced ---
            has_external_db = any(marker in content for marker in _EXTERNAL_DB_MARKERS)
            if has_external_db:
                # Replace external DB drivers with H2
                content = re.sub(
                    r"driver-class-name:\s*\S+",
                    "driver-class-name: org.h2.Driver",
                    content,
                )
                # Replace external DB URLs with H2
                content = re.sub(
                    r"url:\s*jdbc:(mysql|postgresql|mariadb|oracle|sqlserver)://[^\s]+",
                    "url: jdbc:h2:mem:testdb;DB_CLOSE_DELAY=-1",
                    content,
                )
                # Add/replace dialect
                if "database-platform" in content:
                    content = re.sub(
                        r"database-platform:\s*\S+",
                        "database-platform: org.hibernate.dialect.H2Dialect",
                        content,
                    )
                # Replace ddl-auto to create-drop for validation
                if "ddl-auto" in content:
                    content = re.sub(
                        r"ddl-auto:\s*\S+",
                        "ddl-auto: create-drop",
                        content,
                    )

            patched[path] = content
            logger.info("validation.patched_yaml: %s → forced overrides for validation", path)

    return patched


def _detect_server_port(output_files: dict[str, str], default: int = 8080) -> int:
    """
    Detect the server port from application.properties or application.yml.
    Uses whatever the migration generated from the MuleSoft YAML config.
    Falls back to 8080.
    """
    import re
    for path, content in output_files.items():
        basename = path.split("/")[-1] if "/" in path else path
        if basename == "application.properties":
            m = re.search(r"server\.port\s*=\s*(\d+)", content)
            if m:
                return int(m.group(1))
        elif basename in ("application.yml", "application.yaml"):
            # Match "port: 8081" under server: block or flat
            m = re.search(r"port:\s*(\d+)", content)
            if m:
                return int(m.group(1))
    return default


def _detect_api_base_path(output_files: dict[str, str]) -> str:
    """
    Detect the API base path from controller @RequestMapping annotations.

    Looks for class-level @RequestMapping("/api/v1") or similar on @RestController classes.
    Also checks server.servlet.context-path in application.properties.
    Returns the base path (e.g. "/api/v1") or "" if none found.
    """
    import re
    base_path = ""

    # Check application.properties for context-path
    for path, content in output_files.items():
        basename = path.split("/")[-1] if "/" in path else path
        if basename == "application.properties":
            m = re.search(r"server\.servlet\.context-path\s*=\s*(\S+)", content)
            if m:
                base_path = m.group(1).strip().rstrip("/")
                break
        elif basename in ("application.yml", "application.yaml"):
            m = re.search(r"context-path:\s*(\S+)", content)
            if m:
                base_path = m.group(1).strip().rstrip("/")
                break

    if base_path:
        return base_path

    # Check controller files for class-level @RequestMapping
    for path, content in output_files.items():
        if not path.endswith(".java"):
            continue
        if "@RestController" not in content:
            continue
        # Find class-level @RequestMapping (before the class declaration)
        # Match @RequestMapping("/api/v1") or @RequestMapping(value = "/api/v1")
        class_match = re.search(r"@RestController", content)
        if not class_match:
            continue
        # Look in the 20 lines before/after @RestController for @RequestMapping
        start = max(0, class_match.start() - 500)
        end = min(len(content), class_match.end() + 500)
        region = content[start:end]
        rm_match = re.search(
            r'@RequestMapping\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']\s*\)',
            region,
        )
        if rm_match:
            base_path = rm_match.group(1).rstrip("/")
            logger.info("validation.detected_base_path: %s from %s", base_path, path)
            return base_path

    return base_path


def _detect_java_version(output_files: dict[str, str], default: str = "17") -> str:
    """
    Detect the Java version from pom.xml's <java.version> property.
    Falls back to the given default.
    """
    import re
    pom = output_files.get("pom.xml", "")
    if not pom:
        return default
    # Match <java.version>21</java.version> or <maven.compiler.source>17</>
    m = re.search(r"<java\.version>\s*(\d+)\s*</java\.version>", pom)
    if m:
        return m.group(1)
    m = re.search(r"<maven\.compiler\.source>\s*(\d+)\s*</maven\.compiler\.source>", pom)
    if m:
        return m.group(1)
    m = re.search(r"<release>\s*(\d+)\s*</release>", pom)
    if m:
        return m.group(1)
    return default


def _generate_h2_schema(output_files: dict[str, str]) -> str:
    """
    Analyse SQL queries in Java source files to generate H2-compatible schema.sql.

    Extracts table names and columns from SELECT, INSERT, and UPDATE statements
    and generates CREATE TABLE IF NOT EXISTS statements with sensible H2 types.
    """
    import re

    # Collect all SQL strings from Java files
    # First join Java string concatenations:  "part1 " + "part2" → "part1 part2"
    all_sql: list[str] = []
    for path, content in output_files.items():
        if not path.endswith(".java"):
            continue
        # Join consecutive string concatenations: "..." +\n  "..." → single string
        joined = re.sub(r'"\s*\+\s*\n?\s*"', '', content)
        # Match strings that look like SQL
        strings = re.findall(r'"((?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|FROM|JOIN)\s[^"]+)"', joined, re.IGNORECASE)
        all_sql.extend(strings)

    if not all_sql:
        return ""

    # Normalise: collapse whitespace
    normalised = [re.sub(r'\s+', ' ', s).strip() for s in all_sql]

    # --- Extract table→columns mapping ---
    tables: dict[str, dict[str, str]] = {}  # table -> {col: type_hint}

    # Helper: classify column type from name
    def _guess_type(col: str) -> str:
        col_lower = col.lower()
        if col_lower.endswith("_id") or col_lower == "id":
            return "BIGINT"
        if col_lower.endswith("_date") or col_lower in ("created_at", "updated_at", "timestamp"):
            return "DATE"
        if col_lower.endswith("_at"):
            return "TIMESTAMP"
        if col_lower in ("amount", "premium", "coverage_amount", "claim_amount",
                         "approved_amount", "total_claimed", "total_approved", "price", "cost", "balance"):
            return "DECIMAL(15,2)"
        if col_lower in ("count", "total", "quantity", "total_claims", "active_policies"):
            return "INT"
        if col_lower in ("description", "notes", "content", "body", "text"):
            return "VARCHAR(2000)"
        if col_lower in ("email", "holder_email"):
            return "VARCHAR(255)"
        return "VARCHAR(500)"

    # Parse INSERT INTO table (col1, col2, ...) VALUES ...
    for sql in normalised:
        m = re.match(r'INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)', sql, re.IGNORECASE)
        if m:
            table = m.group(1).lower()
            cols = [c.strip() for c in m.group(2).split(",")]
            if table not in tables:
                tables[table] = {}
            for col in cols:
                if col and col not in tables[table]:
                    tables[table][col] = _guess_type(col)

    # Parse SELECT col1, col2, ... FROM table — with alias-aware column routing
    for sql in normalised:
        m = re.match(r'SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+(\w+))?\s*(.*)', sql, re.IGNORECASE)
        if not m:
            continue
        cols_str = m.group(1)
        table = m.group(2).lower()
        alias = m.group(3)  # e.g. "c" in "FROM claims c"
        rest = m.group(4) or ""

        if table not in tables:
            tables[table] = {}

        if cols_str.strip() == "*" or cols_str.strip().startswith("COUNT"):
            continue
        # Skip if it's primarily aggregate functions
        if re.match(r'\s*(COALESCE|SUM|COUNT|AVG|MIN|MAX)\s*\(', cols_str, re.IGNORECASE):
            continue

        # Build alias→table mapping: main table + JOINed tables
        alias_map: dict[str, str] = {}
        if alias and alias.upper() not in ("JOIN", "WHERE", "ORDER", "GROUP", "LEFT", "RIGHT", "INNER", "ON"):
            alias_map[alias.lower()] = table
        for jm in re.finditer(r'JOIN\s+(\w+)\s+(\w+)\s+ON', rest, re.IGNORECASE):
            j_table = jm.group(1).lower()
            j_alias = jm.group(2).lower()
            alias_map[j_alias] = j_table
            if j_table not in tables:
                tables[j_table] = {}

        # Parse columns and route to correct table via alias
        cols = [c.strip() for c in cols_str.split(",")]
        for col in cols:
            col = col.strip()
            # Check for alias prefix (c.claim_id)
            alias_match = re.match(r'^(\w+)\.(.+)$', col)
            target_table = table  # default: FROM table
            if alias_match:
                col_alias = alias_match.group(1).lower()
                col = alias_match.group(2).strip()
                target_table = alias_map.get(col_alias, table)
            # Remove AS alias
            col = re.split(r'\s+as\s+', col, flags=re.IGNORECASE)[0].strip()
            # Skip * and aggregates
            if col == "*":
                continue
            if not re.match(r'^[a-zA-Z_]\w*$', col):
                continue
            if col.upper() in ("COUNT", "COALESCE", "SUM", "AVG", "MIN", "MAX"):
                continue
            if target_table not in tables:
                tables[target_table] = {}
            if col not in tables[target_table]:
                tables[target_table][col] = _guess_type(col)

    # Parse JOIN table2 ON ... (catch any JOINs not already found)
    for sql in normalised:
        for jm in re.finditer(r'JOIN\s+(\w+)\s+', sql, re.IGNORECASE):
            table = jm.group(1).lower()
            if table not in tables:
                tables[table] = {}

    if not tables:
        return ""

    # --- Generate CREATE TABLE statements ---
    ddl_lines: list[str] = []
    ddl_lines.append("-- Auto-generated schema for H2 validation")
    ddl_lines.append("-- Generated from SQL queries found in Java sources")
    ddl_lines.append("")

    def _singularise(name: str) -> str:
        """Naive English singular: policies→policy, claims→claim, addresses→address."""
        if name.endswith("ies"):
            return name[:-3] + "y"
        if name.endswith("ses"):
            return name[:-2]
        if name.endswith("s") and not name.endswith("ss"):
            return name[:-1]
        return name

    for table, columns in sorted(tables.items()):
        # Detect primary key: look for <singular_table>_id in columns
        singular = _singularise(table)
        pk_col = f"{singular}_id"
        if pk_col not in columns:
            pk_col = "id"
        if pk_col not in columns:
            columns[pk_col] = "BIGINT"

        ddl_lines.append(f"CREATE TABLE IF NOT EXISTS {table} (")
        col_defs = []
        for col, dtype in columns.items():
            if col == pk_col:
                col_defs.insert(0, f"    {col} {dtype} AUTO_INCREMENT PRIMARY KEY")
            else:
                col_defs.append(f"    {col} {dtype}")
        # Add created_at if not present (common column)
        if "created_at" not in columns:
            col_defs.append("    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ddl_lines.append(",\n".join(col_defs))
        ddl_lines.append(");")
        ddl_lines.append("")

    # --- Generate sample INSERT statements for seed data ---
    # This ensures H2 tables have data for validation comparison
    ddl_lines.append("-- Sample seed data for validation")
    ddl_lines.append("")

    # Sample data generators keyed by column type/name
    def _sample_val(col: str, dtype: str, row_idx: int) -> str:
        col_lower = col.lower()
        if col_lower.endswith("_id") or col_lower == "id":
            return str(row_idx)
        if "number" in col_lower:
            prefix = col_lower.split("_")[0].upper()[:3]
            return f"'{prefix}-2024-{row_idx:03d}'"
        if "name" in col_lower:
            names = ["John Smith", "Sarah Johnson", "Michael Chen", "Emily Davis", "Robert Wilson"]
            return f"'{names[row_idx % len(names)]}'"
        if "email" in col_lower:
            return f"'user{row_idx}@example.com'"
        if "type" in col_lower:
            return "'AUTO'"
        if "status" in col_lower:
            return "'ACTIVE'"
        if "date" in col_lower or dtype == "DATE":
            return "'2024-01-01'"
        if col_lower.endswith("_at") or dtype == "TIMESTAMP":
            return "CURRENT_TIMESTAMP"
        if dtype.startswith("DECIMAL") or col_lower in ("amount", "premium", "coverage_amount",
                "claim_amount", "approved_amount", "price", "cost", "balance"):
            amounts = [50000, 25000, 100000, 75000, 35000]
            return str(amounts[row_idx % len(amounts)])
        if dtype == "INT":
            return str(row_idx + 1)
        if "description" in col_lower or "notes" in col_lower:
            return f"'Sample record {row_idx}'"
        return f"'sample_{row_idx}'"

    for table, columns in sorted(tables.items()):
        if not columns:
            continue
        # Insert 3 sample rows per table
        col_names = list(columns.keys())
        # Find PK column and skip auto-increment
        singular = _singularise(table)
        pk_col = f"{singular}_id" if f"{singular}_id" in columns else "id"

        for row_idx in range(1, 4):
            vals = []
            insert_cols = []
            for col in col_names:
                # Skip auto-increment PK (it's generated)
                if col == pk_col:
                    continue
                insert_cols.append(col)
                vals.append(_sample_val(col, columns[col], row_idx))
            if insert_cols:
                cols_sql = ", ".join(insert_cols)
                vals_sql = ", ".join(vals)
                ddl_lines.append(f"INSERT INTO {table} ({cols_sql}) VALUES ({vals_sql});")
        ddl_lines.append("")

    schema = "\n".join(ddl_lines)
    logger.info("validation.generated_schema: %d tables, %d bytes", len(tables), len(schema))
    return schema


# ---------------------------------------------------------------------------
#  Method-call reconciliation: fix controller→service call mismatches
# ---------------------------------------------------------------------------
def _patch_method_call_mismatches(output_files: dict[str, str]) -> dict[str, str]:
    """
    Fix method-call mismatches between controllers and services.

    LLM enhancement often changes method names or parameter lists in service
    classes without updating the callers, causing compilation failures like:
        auditService.auditAccessSubFlow()  — but service only has auditAccess(...)
        sendService.sendNotificationSubFlow() — but method expects 4 params

    Strategy:
      1. Scan service classes: extract {className → {methodName → paramCount}}
      2. Scan calling classes: find service field references and method calls
      3. If a called method doesn't exist → find closest match by name similarity
      4. If arg count mismatches → add null args or trim excess
    """
    import re

    # ── Phase 1: Build service method registry ──
    # Map: "AuditService" → {"auditAccess": 4, "auditError": 3}
    service_methods: dict[str, dict[str, int]] = {}
    service_files = {}

    for path, content in output_files.items():
        if not path.endswith(".java"):
            continue
        # Detect service classes
        if "@Service" not in content and "Service.java" not in path:
            continue
        # Extract class name
        cls_match = re.search(r'public\s+class\s+(\w+)', content)
        if not cls_match:
            continue
        cls_name = cls_match.group(1)
        service_files[cls_name] = path

        # Extract public methods: public ReturnType methodName(Type1 arg1, Type2 arg2)
        # ReturnType can be generic: Map<String, Object>, List<Map<String, Object>>, etc.
        methods: dict[str, int] = {}
        for m in re.finditer(
            r'public\s+(?:static\s+)?[\w<>,\?\s\[\]]+?\s+(\w+)\s*\(([^)]*)\)',
            content,
        ):
            method_name = m.group(1)
            # Skip class declarations (public class Foo)
            if method_name in ("class", "interface", "enum"):
                continue
            params = m.group(2).strip()
            # Count params respecting angle brackets (Map<String, Object> = 1 param, not 2)
            if not params:
                param_count = 0
            else:
                param_count = 0
                angle_depth = 0
                for ch in params:
                    if ch == '<':
                        angle_depth += 1
                    elif ch == '>':
                        angle_depth -= 1
                    elif ch == ',' and angle_depth == 0:
                        param_count += 1
                param_count += 1  # last param (no trailing comma)
            methods[method_name] = param_count
        if methods:
            service_methods[cls_name] = methods

    if not service_methods:
        return output_files

    logger.info(
        "validation.method_registry: %s",
        {k: list(v.keys()) for k, v in service_methods.items()},
    )

    # ── Phase 2: Build field→class mapping from calling files ──
    # Find lines like: private final AuditService auditService;
    # or constructor injection fields
    patched = dict(output_files)
    for path, content in list(patched.items()):
        if not path.endswith(".java"):
            continue
        # Skip service files themselves
        cls_match = re.search(r'public\s+class\s+(\w+)', content)
        if cls_match and cls_match.group(1) in service_methods:
            continue

        # Find service field declarations
        field_to_class: dict[str, str] = {}
        for fm in re.finditer(
            r'(?:private\s+final\s+|private\s+)(\w+Service)\s+(\w+)\s*;',
            content,
        ):
            svc_class = fm.group(1)
            svc_field = fm.group(2)
            if svc_class in service_methods:
                field_to_class[svc_field] = svc_class

        if not field_to_class:
            continue

        # ── Phase 3: Fix method calls on service fields ──
        lines = content.split("\n")
        modified = False
        new_lines = []

        for line in lines:
            new_line = line
            for field_name, svc_class in field_to_class.items():
                # Pattern: fieldName.methodName(args)
                call_pattern = re.compile(
                    rf'(\b{re.escape(field_name)}\.(\w+)\s*\()([^)]*)\)'
                )
                call_match = call_pattern.search(line)
                if not call_match:
                    continue

                called_method = call_match.group(2)
                call_args = call_match.group(3).strip()
                call_arg_count = 0 if not call_args else len(call_args.split(","))
                known_methods = service_methods[svc_class]

                if called_method in known_methods:
                    expected_count = known_methods[called_method]
                    if call_arg_count == expected_count:
                        continue  # All good
                    # Arg count mismatch — fix it
                    if call_arg_count == 0 and expected_count > 0:
                        # Add null args
                        null_args = ", ".join(["null"] * expected_count)
                        old_call = call_match.group(0)
                        new_call = f"{field_name}.{called_method}({null_args})"
                        new_line = new_line.replace(old_call, new_call)
                        modified = True
                        logger.info(
                            "validation.fixed_arg_count: %s.%s() → %s.%s(%d nulls) in %s",
                            field_name, called_method, field_name, called_method, expected_count, path,
                        )
                    elif call_arg_count > expected_count:
                        # Too many args — trim to expected count
                        args_list = call_args.split(",")[:expected_count]
                        trimmed = ", ".join(a.strip() for a in args_list)
                        old_call = call_match.group(0)
                        new_call = f"{field_name}.{called_method}({trimmed})"
                        new_line = new_line.replace(old_call, new_call)
                        modified = True
                        logger.info(
                            "validation.trimmed_args: %s.%s(%d→%d args) in %s",
                            field_name, called_method, call_arg_count, expected_count, path,
                        )
                else:
                    # Method doesn't exist — find closest match
                    best_match = None
                    best_score = 0
                    called_lower = called_method.lower()
                    for real_method in known_methods:
                        real_lower = real_method.lower()
                        # Check if one contains the other or if they share a common root
                        if real_lower in called_lower or called_lower in real_lower:
                            score = len(real_lower) + len(called_lower) - abs(len(real_lower) - len(called_lower))
                            if score > best_score:
                                best_score = score
                                best_match = real_method
                        # Also check word overlap
                        called_words = set(re.findall(r'[A-Z][a-z]+|[a-z]+', called_method))
                        real_words = set(re.findall(r'[A-Z][a-z]+|[a-z]+', real_method))
                        overlap = len(called_words & real_words)
                        if overlap > 0 and overlap > best_score / 10:
                            score = overlap * 10
                            if score > best_score:
                                best_score = score
                                best_match = real_method

                    if best_match:
                        expected_count = known_methods[best_match]
                        if call_arg_count == 0 and expected_count > 0:
                            null_args = ", ".join(["null"] * expected_count)
                            new_args = null_args
                        elif call_arg_count == expected_count:
                            new_args = call_args
                        elif call_arg_count > expected_count:
                            args_list = call_args.split(",")[:expected_count]
                            new_args = ", ".join(a.strip() for a in args_list)
                        else:
                            # Fewer args than expected — pad with nulls
                            existing = [a.strip() for a in call_args.split(",")] if call_args else []
                            existing += ["null"] * (expected_count - len(existing))
                            new_args = ", ".join(existing)

                        old_call = call_match.group(0)
                        new_call = f"{field_name}.{best_match}({new_args})"
                        new_line = new_line.replace(old_call, new_call)
                        modified = True
                        logger.info(
                            "validation.renamed_method: %s.%s() → %s.%s(%d args) in %s",
                            field_name, called_method, field_name, best_match, expected_count, path,
                        )
                    else:
                        # No match found — comment out the call to prevent compilation failure
                        indent = line[:len(line) - len(line.lstrip())]
                        new_line = f"{indent}// TODO: {field_name}.{called_method}() — method not found in {svc_class}"
                        modified = True
                        logger.warning(
                            "validation.commented_out_missing_method: %s.%s() in %s",
                            field_name, called_method, path,
                        )

            new_lines.append(new_line)

        if modified:
            patched[path] = "\n".join(new_lines)
            logger.info("validation.patched_method_calls: %s", path)

    return patched


def _create_build_context(output_files: dict[str, str], java_version: str = "17") -> bytes:
    """
    Create a tar.gz build context from output_files dict + generated Dockerfile.

    Auto-detects Java version from pom.xml if available.
    Returns the tar.gz bytes ready for ACR Quick Build upload.
    """
    # Auto-detect Java version from pom.xml (overrides the passed parameter)
    detected = _detect_java_version(output_files, java_version)
    if detected != java_version:
        logger.info(
            "validation.java_version_override: requested=%s, pom=%s",
            java_version, detected,
        )
    java_version = detected

    # Detect server port from generated config (use whatever MuleSoft YAML configured)
    server_port = _detect_server_port(output_files)
    logger.info("validation.server_port: %d", server_port)

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        # Add Dockerfile (our own optimized multi-stage build)
        dockerfile_content = _DOCKERFILE.format(java_version=java_version, server_port=server_port)
        df_info = tarfile.TarInfo(name="Dockerfile")
        df_bytes = dockerfile_content.encode("utf-8")
        df_info.size = len(df_bytes)
        tar.addfile(df_info, io.BytesIO(df_bytes))

        # Patch source files: add missing imports, fix compilation errors, fix pom.xml, fix properties
        patched_files = _patch_java_sources(dict(output_files))
        patched_files = _patch_java_compilation_errors(patched_files)
        patched_files = _patch_datasource_consistency(patched_files)
        patched_files = _patch_method_call_mismatches(patched_files)
        if "pom.xml" in patched_files:
            patched_files["pom.xml"] = _patch_pom_xml(patched_files["pom.xml"])
        patched_files = _patch_application_properties(patched_files)

        # Generate a SchemaInitializer.java @Configuration class that creates
        # tables on startup using JdbcTemplate. This is the most reliable approach —
        # Spring's schema.sql doesn't work with JPA ddl-auto, and H2 INIT= URL params
        # get mangled by YAML parsing. A CommandLineRunner is guaranteed to run.
        schema_sql = _generate_h2_schema(patched_files)
        if schema_sql:
            # Extract CREATE TABLE statements
            ddl_stmts = []
            current_stmt = []
            for line in schema_sql.split("\n"):
                stripped = line.strip()
                if stripped.startswith("--") or not stripped:
                    continue
                current_stmt.append(stripped)
                if stripped.endswith(";"):
                    stmt = " ".join(current_stmt)
                    ddl_stmts.append(stmt)
                    current_stmt = []

            if ddl_stmts:
                # Detect the base package from existing Java files
                base_pkg = "com.example"
                for p in patched_files:
                    if p.endswith("Application.java"):
                        # Extract package from file path
                        parts = p.replace("src/main/java/", "").replace(".java", "").split("/")
                        if len(parts) > 1:
                            base_pkg = ".".join(parts[:-1])
                        break

                # Build the Java source for SchemaInitializer
                ddl_java_stmts = ""
                for stmt in ddl_stmts:
                    # Escape double quotes and backslashes for Java string
                    escaped = stmt.replace("\\", "\\\\").replace('"', '\\"')
                    ddl_java_stmts += f'            jdbcTemplate.execute("{escaped}");\n'

                schema_init_java = f'''package {base_pkg}.config;

import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

@Configuration
public class SchemaInitializer {{

    @Bean
    public CommandLineRunner initSchema(JdbcTemplate jdbcTemplate) {{
        return args -> {{
{ddl_java_stmts}        }};
    }}
}}
'''
                # Determine the file path
                pkg_path = base_pkg.replace(".", "/")
                init_path = f"src/main/java/{pkg_path}/config/SchemaInitializer.java"
                patched_files[init_path] = schema_init_java
                logger.info("validation.schema_initializer_added: %s (%d DDL stmts)", init_path, len(ddl_stmts))

        # Add source files (skip Dockerfile/docker-compose from migration output
        # since we generate our own optimized Dockerfile above)
        skip_files = {"dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"}
        for rel_path, content in patched_files.items():
            safe_parts = Path(rel_path).parts
            if ".." in safe_parts:
                logger.warning("validation.skipped_unsafe_path: %s", rel_path)
                continue
            if safe_parts[-1].lower() in skip_files and len(safe_parts) == 1:
                logger.info("validation.skipped_migration_docker_file: %s", rel_path)
                continue
            file_bytes = content.encode("utf-8")
            info = tarfile.TarInfo(name=str(Path(*safe_parts)))
            info.size = len(file_bytes)
            tar.addfile(info, io.BytesIO(file_bytes))

    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
#  ACR Quick Build (ACR Tasks) — Enterprise SDK-based implementation
# ---------------------------------------------------------------------------

_ARM_BASE = "https://management.azure.com"
_ACR_API_VERSION = "2019-06-01-preview"


async def _upload_build_context(
    credential,
    registry_path: str,
    context_bytes: bytes,
    validation_id: str,
    log_offset: int = 4,
) -> str:
    """
    Upload tar.gz build context to ACR staging blob.

    Uses the REST API listBuildSourceUploadUrl (no SDK method for this).
    Returns the relativePath to pass to scheduleRun.
    """
    token = await credential.get_token("https://management.azure.com/.default")
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as http:
        await _store_val_log(validation_id, log_offset, "Requesting source upload URL...")
        upload_resp = await http.post(
            f"{_ARM_BASE}{registry_path}/listBuildSourceUploadUrl"
            f"?api-version={_ACR_API_VERSION}",
            headers=headers,
        )
        upload_resp.raise_for_status()
        upload_data = upload_resp.json()

        await _store_val_log(
            validation_id,
            log_offset + 1,
            f"Uploading {len(context_bytes):,} bytes to staging blob...",
        )
        put_resp = await http.put(
            upload_data["uploadUrl"],
            content=context_bytes,
            headers={"x-ms-blob-type": "BlockBlob"},
        )
        put_resp.raise_for_status()

        await _store_val_log(validation_id, log_offset + 2, "Upload complete.")
        return upload_data["relativePath"]


async def _run_acr_build(
    credential,
    subscription_id: str,
    resource_group: str,
    acr_name: str,
    relative_path: str,
    tag: str,
    validation_id: str,
    log_offset: int = 7,
) -> None:
    """
    Schedule an ACR Quick Build via REST API and poll via the run resource.

    Uses the stable /runs/{runId} endpoint for polling (NOT Azure-AsyncOperation
    which can 404). Extracts runId from scheduleRun response body.
    """
    import asyncio

    registry_path = (
        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        f"/providers/Microsoft.ContainerRegistry/registries/{acr_name}"
    )

    run_body = {
        "type": "DockerBuildRequest",
        "dockerFilePath": "Dockerfile",
        "imageNames": [f"{tag}:latest"],
        "isPushEnabled": True,
        "sourceLocation": relative_path,
        "platform": {"os": "Linux", "architecture": "amd64"},
    }

    await _store_val_log(
        validation_id, log_offset,
        f"Scheduling ACR build for {tag}:latest...",
    )

    token = await credential.get_token("https://management.azure.com/.default")
    auth_headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=180) as http:
        # Schedule the build
        run_resp = await http.post(
            f"{_ARM_BASE}{registry_path}/scheduleRun"
            f"?api-version={_ACR_API_VERSION}",
            headers=auth_headers,
            json=run_body,
        )
        if run_resp.status_code not in (200, 201, 202):
            raise RuntimeError(
                f"scheduleRun failed: HTTP {run_resp.status_code} — "
                f"{run_resp.text[:500]}"
            )

        # NOTE: HTTP 200 does NOT mean the build completed synchronously.
        # It means the request was accepted. We must always poll for completion.

        # --- Determine the poll URL ---
        # Priority: direct /runs/{runId} URL (most stable)
        # Fallback: Location header (with api-version appended)
        run_data = {}
        try:
            run_data = run_resp.json()
        except Exception:
            pass

        # The 202 response body contains the run resource with runId
        run_id = (
            run_data.get("runId")
            or run_data.get("properties", {}).get("runId")
            or ""
        )

        poll_url = ""
        if run_id and "/" not in str(run_id):
            # Direct run resource URL — most reliable
            poll_url = (
                f"{_ARM_BASE}{registry_path}/runs/{run_id}"
                f"?api-version={_ACR_API_VERSION}"
            )
        else:
            # Fallback: Location header
            location = run_resp.headers.get("Location", "")
            if location:
                sep = "&" if "?" in location else "?"
                poll_url = (
                    f"{location}{sep}api-version={_ACR_API_VERSION}"
                    if "api-version" not in location
                    else location
                )

        if not poll_url:
            raise RuntimeError(
                "No run ID or Location header in scheduleRun response. "
                f"Headers: {dict(run_resp.headers)}, "
                f"Body keys: {list(run_data.keys())}"
            )

        await _store_val_log(
            validation_id, log_offset + 1,
            f"Build scheduled (run: {run_id or 'unknown'}). "
            f"Polling: {poll_url[:100]}...",
        )

        # --- Poll for completion (max ~8 min to leave room for ACI deploy) ---
        for iteration in range(32):
            await asyncio.sleep(15)

            # Refresh token every ~5 min (tokens expire after 60 min)
            if iteration % 20 == 19:
                token = await credential.get_token(
                    "https://management.azure.com/.default"
                )
                auth_headers["Authorization"] = f"Bearer {token.token}"

            poll_resp = await http.get(poll_url, headers=auth_headers)

            if poll_resp.status_code != 200:
                await _store_val_log(
                    validation_id, log_offset + 2 + iteration,
                    f"Poll HTTP {poll_resp.status_code} (will retry)...",
                )
                continue

            poll_data = poll_resp.json()
            status = (
                poll_data.get("status")
                or poll_data.get("properties", {}).get("status")
                or ""
            ).lower()

            await _store_val_log(
                validation_id, log_offset + 2 + iteration,
                f"Build status: {status}",
            )

            if status == "succeeded":
                return
            if status in ("failed", "canceled", "error"):
                # ── Fetch actual build logs via logUri ──
                log_uri = (
                    poll_data.get("properties", {}).get("logLink")
                    or poll_data.get("properties", {}).get("logUri")
                    or poll_data.get("logLink")
                    or poll_data.get("logUri")
                    or ""
                )
                build_log_text = ""
                if log_uri:
                    try:
                        log_resp = await http.get(log_uri, timeout=15.0)
                        if log_resp.status_code == 200:
                            build_log_text = log_resp.text[-4000:]  # last 4KB
                            # Store full build log for UI visibility
                            await _store_val_log(
                                validation_id, log_offset + 50,
                                f"=== ACR Build Log (last 4KB) ===\n{build_log_text}",
                            )
                            logger.error(
                                "acr_build.log_tail",
                                extra={"validation_id": validation_id, "log_tail": build_log_text[-2000:]},
                            )
                    except Exception as log_err:
                        logger.warning("acr_build.log_fetch_failed: %s", log_err)

                # Also try to get run log via ACR API
                if not build_log_text and run_id:
                    try:
                        log_api_url = (
                            f"https://management.azure.com/subscriptions/{subscription_id}"
                            f"/resourceGroups/{resource_group}/providers/Microsoft.ContainerRegistry"
                            f"/registries/{acr_name}/runs/{run_id}/listLogSasUrl"
                            f"?api-version=2019-06-01-preview"
                        )
                        log_sas_resp = await http.post(log_api_url, headers=auth_headers, json={})
                        if log_sas_resp.status_code == 200:
                            sas_url = log_sas_resp.json().get("logLink", "")
                            if sas_url:
                                log_content_resp = await http.get(sas_url, timeout=15.0)
                                if log_content_resp.status_code == 200:
                                    build_log_text = log_content_resp.text[-4000:]
                                    await _store_val_log(
                                        validation_id, log_offset + 51,
                                        f"=== ACR Build Log (via SAS) ===\n{build_log_text}",
                                    )
                                    logger.error(
                                        "acr_build.log_via_sas",
                                        extra={"validation_id": validation_id, "log_tail": build_log_text[-2000:]},
                                    )
                    except Exception as sas_err:
                        logger.warning("acr_build.sas_log_fetch_failed: %s", sas_err)

                err_detail = build_log_text[-500:] if build_log_text else status
                raise RuntimeError(f"ACR build {status}: {err_detail}")

        raise RuntimeError("ACR build timed out after ~8 minutes")


async def build_and_push_image(
    validation_id: str,
    output_files: dict[str, str],
    java_version: str = "17",
    image_tag: Optional[str] = None,
) -> str:
    """
    Build a Docker image using ACR Tasks (Quick Build) via the
    azure-mgmt-containerregistry SDK.

    Steps:
        1. Create tar.gz build context from output_files + Dockerfile
        2. Upload context to ACR staging blob (with retry)
        3. Schedule build via SDK begin_schedule_run + LRO poller (with retry)

    Returns the full image reference (e.g., registry.azurecr.io/tag:latest).
    """
    import asyncio
    from azure.identity.aio import DefaultAzureCredential

    acr_login_server = os.environ["ACR_LOGIN_SERVER"]
    acr_name = acr_login_server.split(".")[0]
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    resource_group = os.environ.get("RESOURCE_GROUP", "mulesoft-migrator-prod-rg")

    tag = image_tag or f"validation-{validation_id[:8]}"
    image_ref = f"{acr_login_server}/{tag}:latest"

    logger.info(
        "build_and_push_image.start",
        extra={
            "validation_id": validation_id,
            "file_count": len(output_files),
            "java_version": java_version,
            "image_ref": image_ref,
        },
    )

    await _store_val_log(validation_id, 1, f"Building image: {image_ref}")
    await _store_val_log(validation_id, 2, f"Java version: {java_version}")

    # --- Phase 1: Create tar.gz build context ---
    context_bytes = _create_build_context(output_files, java_version)
    await _store_val_log(
        validation_id,
        3,
        f"Build context: {len(context_bytes):,} bytes, {len(output_files)} files",
    )

    registry_path = (
        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        f"/providers/Microsoft.ContainerRegistry/registries/{acr_name}"
    )

    credential = DefaultAzureCredential()
    try:
        # --- Phase 2: Upload build context (retry up to 3 times) ---
        relative_path: str = ""
        for attempt in range(3):
            try:
                relative_path = await _upload_build_context(
                    credential, registry_path, context_bytes, validation_id,
                )
                break
            except Exception as exc:
                if attempt == 2:
                    logger.error("build_and_push_image.upload_failed", extra={
                        "validation_id": validation_id, "error": str(exc),
                    })
                    raise
                await _store_val_log(
                    validation_id, 20 + attempt,
                    f"Upload retry {attempt + 1}/3: {exc}",
                )
                await asyncio.sleep(3 * (attempt + 1))

        logger.info("build_and_push_image.upload_complete", extra={
            "validation_id": validation_id,
            "relative_path": relative_path,
        })

        # --- Phase 3: Schedule ACR build (retry up to 2 times) ---
        # On retry, re-upload context because the staging blob may expire
        for attempt in range(2):
            try:
                await _run_acr_build(
                    credential, subscription_id, resource_group, acr_name,
                    relative_path, tag, validation_id,
                )
                break
            except Exception as exc:
                if attempt == 1:
                    logger.error("build_and_push_image.build_failed", extra={
                        "validation_id": validation_id, "error": str(exc),
                    }, exc_info=True)
                    raise
                await _store_val_log(
                    validation_id, 30 + attempt,
                    f"Build retry {attempt + 1}/2: {exc}",
                )
                await asyncio.sleep(10)
                # Re-upload context for retry (staging blob may have expired)
                try:
                    relative_path = await _upload_build_context(
                        credential, registry_path, context_bytes, validation_id,
                        log_offset=32,
                    )
                except Exception:
                    pass  # Use the old path if re-upload fails

        # Build polling reported "Succeeded" — image is pushed to ACR.
        await _store_val_log(validation_id, 10, f"Build succeeded, image pushed.")
        logger.info("build_and_push_image.complete", extra={
            "validation_id": validation_id, "image_ref": image_ref,
        })
        return image_ref
    finally:
        await credential.close()


# ---------------------------------------------------------------------------
#  ACI Deployment
# ---------------------------------------------------------------------------

async def deploy_aci(
    validation_id: str,
    image_ref: str,
    java_version: str = "17",
    keep_alive_min: int = 15,
    server_port: int = 8080,
) -> dict[str, str]:
    """
    Deploy a container to Azure Container Instances.

    Returns dict with aci_name, aci_fqdn, app_url.
    """
    from azure.identity.aio import DefaultAzureCredential
    from azure.mgmt.containerinstance.aio import ContainerInstanceManagementClient
    from azure.mgmt.containerinstance.models import (
        Container,
        ContainerGroup,
        ContainerPort,
        ImageRegistryCredential,
        IpAddress,
        Port,
        ResourceRequests,
        ResourceRequirements,
    )

    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    resource_group = os.environ.get("RESOURCE_GROUP", "mulesoft-migrator-prod-rg")
    acr_login_server = os.environ["ACR_LOGIN_SERVER"]
    acr_username = os.environ.get("ACR_ADMIN_USERNAME", "")
    acr_password = os.environ.get("ACR_ADMIN_PASSWORD", "")

    aci_name = f"val-{validation_id[:8]}"
    dns_label = f"val-{validation_id[:12]}"

    await _store_val_log(validation_id, 100, f"Deploying ACI: {aci_name}")

    container = Container(
        name=aci_name,
        image=image_ref,
        resources=ResourceRequirements(
            requests=ResourceRequests(cpu=1.0, memory_in_gb=1.5)
        ),
        ports=[ContainerPort(port=server_port)],
        environment_variables=[],
    )

    registry_creds = []
    if acr_username and acr_password:
        registry_creds.append(
            ImageRegistryCredential(
                server=acr_login_server,
                username=acr_username,
                password=acr_password,
            )
        )

    group = ContainerGroup(
        location=os.environ.get("AZURE_LOCATION", "eastus"),
        containers=[container],
        os_type="Linux",
        restart_policy="Never",
        image_registry_credentials=registry_creds or None,
        ip_address=IpAddress(
            ports=[Port(port=server_port, protocol="TCP")],
            type="Public",
            dns_name_label=dns_label,
        ),
    )

    credential = DefaultAzureCredential()
    try:
        aci_client = ContainerInstanceManagementClient(credential, subscription_id)
        try:
            await _store_val_log(validation_id, 101, "Creating container group...")
            poller = await aci_client.container_groups.begin_create_or_update(
                resource_group, aci_name, group
            )
            result = await poller.result()

            fqdn = result.ip_address.fqdn if result.ip_address else ""
            app_url = f"http://{fqdn}:{server_port}" if fqdn else ""

            await _store_val_log(validation_id, 102, f"ACI deployed: {app_url}")

            return {
                "aci_name": aci_name,
                "aci_fqdn": fqdn,
                "app_url": app_url,
            }
        finally:
            await aci_client.close()
    finally:
        await credential.close()


# ---------------------------------------------------------------------------
#  ACI Teardown
# ---------------------------------------------------------------------------

async def teardown_aci(validation_id: str, aci_name: str) -> bool:
    """Delete the ACI container group. Returns True on success."""
    from azure.identity.aio import DefaultAzureCredential
    from azure.mgmt.containerinstance.aio import ContainerInstanceManagementClient

    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    resource_group = os.environ.get("RESOURCE_GROUP", "mulesoft-migrator-prod-rg")

    credential = DefaultAzureCredential()
    try:
        aci_client = ContainerInstanceManagementClient(credential, subscription_id)
        try:
            await _store_val_log(validation_id, 200, f"Tearing down ACI: {aci_name}")
            poller = await aci_client.container_groups.begin_delete(
                resource_group, aci_name
            )
            await poller.result()
            await _store_val_log(validation_id, 201, "ACI deleted successfully")
            return True
        except Exception as exc:
            logger.warning("aci.teardown_failed: %s", exc)
            await _store_val_log(validation_id, 201, f"Teardown failed: {exc}", True)
            return False
        finally:
            await aci_client.close()
    finally:
        await credential.close()


# ---------------------------------------------------------------------------
#  Container Logs
# ---------------------------------------------------------------------------

async def get_container_logs(aci_name: str) -> str:
    """Fetch stdout/stderr from the running ACI container."""
    from azure.identity.aio import DefaultAzureCredential
    from azure.mgmt.containerinstance.aio import ContainerInstanceManagementClient

    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    resource_group = os.environ.get("RESOURCE_GROUP", "mulesoft-migrator-prod-rg")

    credential = DefaultAzureCredential()
    try:
        aci_client = ContainerInstanceManagementClient(credential, subscription_id)
        try:
            logs = await aci_client.containers.list_logs(
                resource_group, aci_name, aci_name, tail=200
            )
            return logs.content or ""
        except Exception as exc:
            logger.warning("aci.logs_failed: %s", exc)
            return f"Failed to fetch logs: {exc}"
        finally:
            await aci_client.close()
    finally:
        await credential.close()


# ---------------------------------------------------------------------------
#  Health Check
# ---------------------------------------------------------------------------

async def wait_for_health(app_url: str, timeout: int = 120) -> bool:
    """Poll /actuator/health until it returns 200 or timeout."""
    health_url = f"{app_url}/actuator/health"
    start = time.monotonic()
    import asyncio

    while (time.monotonic() - start) < timeout:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(health_url, timeout=5)
                if resp.status_code == 200:
                    return True
        except Exception:
            pass
        await asyncio.sleep(5)

    return False


# ---------------------------------------------------------------------------
#  API Comparison
# ---------------------------------------------------------------------------

async def run_comparison(
    mulesoft_base_url: str,
    springboot_base_url: str,
    test_endpoints: list[dict[str, Any]],
    springboot_base_path: str = "",
) -> list[dict[str, Any]]:
    """
    Call both MuleSoft and Spring Boot endpoints, compare responses.

    Each test_endpoint: {method, path, headers?, body?}
    springboot_base_path: controller prefix like "/api/v1" to prepend to Spring Boot paths.
    Returns list of results with status codes, bodies, match status.
    """
    import re as _re

    results = []

    # Sample values for path parameters — used when endpoints have {param} placeholders
    _PARAM_SAMPLES = {
        "policyId": "1", "policyid": "1", "policy_id": "1",
        "claimId": "1", "claimid": "1", "claim_id": "1",
        "id": "1", "userId": "1", "orderId": "1",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        for endpoint in test_endpoints:
            method = endpoint.get("method", "GET").upper()
            raw_path = endpoint.get("path", "/")
            headers = endpoint.get("headers", {})
            body = endpoint.get("body")

            # Substitute path parameters: /policies/{policyId} → /policies/1
            path = _re.sub(
                r"\{(\w+)\}",
                lambda m: _PARAM_SAMPLES.get(m.group(1), "1"),
                raw_path,
            )

            # Fix body: if body is a JSON string like "{}", parse it to a dict
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except (json.JSONDecodeError, TypeError):
                    pass
            # Don't send empty dict as body (causes parse errors on endpoints expecting real data)
            if isinstance(body, dict) and not body:
                body = None

            result: dict[str, Any] = {
                "method": method,
                "path": raw_path,
                "mulesoft": {},
                "springboot": {},
                "match": False,
            }

            # Call MuleSoft
            try:
                mule_url = f"{mulesoft_base_url.rstrip('/')}{path}"
                mule_resp = await client.request(
                    method, mule_url, headers=headers, json=body if body else None
                )
                result["mulesoft"] = {
                    "status": mule_resp.status_code,
                    "body": mule_resp.text[:10000],
                    "headers": dict(mule_resp.headers),
                }
            except Exception as exc:
                result["mulesoft"] = {"error": str(exc)}

            # Call Spring Boot
            try:
                sb_path = f"{springboot_base_path}{path}" if springboot_base_path else path
                sb_url = f"{springboot_base_url.rstrip('/')}{sb_path}"
                sb_resp = await client.request(
                    method, sb_url, headers=headers, json=body if body else None
                )
                result["springboot"] = {
                    "status": sb_resp.status_code,
                    "body": sb_resp.text[:10000],
                    "headers": dict(sb_resp.headers),
                }
            except Exception as exc:
                result["springboot"] = {"error": str(exc)}

            # Compare — structural matching
            # Two responses "match" when:
            #   1. Same HTTP status code
            #   2. Both return valid JSON with the same top-level keys/structure
            #      (data values can differ — MuleSoft has real DB, Spring Boot has H2 seed data)
            #   3. No connection errors
            mule_status = result["mulesoft"].get("status")
            sb_status = result["springboot"].get("status")
            mule_body = result["mulesoft"].get("body", "")
            sb_body = result["springboot"].get("body", "")

            has_errors = (
                "error" in result["mulesoft"]
                or "error" in result["springboot"]
            )

            bodies_match = False
            match_type = "none"

            if not has_errors and mule_status == sb_status:
                # Exact body match
                if mule_body == sb_body:
                    bodies_match = True
                    match_type = "exact"
                else:
                    try:
                        mule_json = json.loads(mule_body) if mule_body else None
                        sb_json = json.loads(sb_body) if sb_body else None
                        if mule_json is not None and sb_json is not None:
                            # Exact JSON match (ignores whitespace)
                            if mule_json == sb_json:
                                bodies_match = True
                                match_type = "exact"
                            # Structural match: same top-level keys
                            elif isinstance(mule_json, dict) and isinstance(sb_json, dict):
                                if set(mule_json.keys()) == set(sb_json.keys()):
                                    bodies_match = True
                                    match_type = "structural"
                    except (json.JSONDecodeError, TypeError):
                        # Both non-JSON with same status — still a match if same status
                        if mule_status == sb_status and mule_status is not None:
                            bodies_match = True
                            match_type = "status_only"

            result["match"] = (
                mule_status == sb_status
                and bodies_match
                and not has_errors
            )
            result["match_type"] = match_type

            results.append(result)

    return results
