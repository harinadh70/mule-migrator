"""
Build & Test Service

Handles:
  - Writing generated project files to a temp directory
  - Maven wrapper generation (no Maven installation needed)
  - JAR / WAR builds via mvnw
  - Docker image builds with multi-platform support
  - Test execution with streaming output
  - Java and Docker prerequisite checks
"""
import os
import json
import shutil
import subprocess
import tempfile
import threading
import uuid
import time
import logging

logger = logging.getLogger(__name__)

# In-memory store for active builds
_builds = {}

DOCKER_PLATFORMS = {
    "linux-amd64": {
        "platform": "linux/amd64",
        "base": "eclipse-temurin:17-jdk-alpine",
        "label": "Linux (x86_64)",
    },
    "ubuntu": {
        "platform": "linux/amd64",
        "base": "eclipse-temurin:17-jdk-focal",
        "label": "Ubuntu",
    },
    "redhat": {
        "platform": "linux/amd64",
        "base": "eclipse-temurin:17-jdk-ubi9-minimal",
        "label": "Red Hat (UBI9)",
    },
    "mac-arm": {
        "platform": "linux/arm64",
        "base": "eclipse-temurin:17-jdk-alpine",
        "label": "macOS (Apple Silicon)",
    },
    "windows": {
        "platform": "linux/amd64",
        "base": "eclipse-temurin:17-jdk-nanoserver-ltsc2022",
        "label": "Windows Server",
    },
}

MAVEN_WRAPPER_PROPERTIES = """distributionUrl=https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.6/apache-maven-3.9.6-bin.zip
wrapperUrl=https://repo.maven.apache.org/maven2/org/apache/maven/wrapper/maven-wrapper/3.2.0/maven-wrapper-3.2.0.jar
"""

MVNW_SCRIPT = r"""#!/bin/sh
# Maven Wrapper bootstrap script
set -e
MAVEN_PROJECTBASEDIR="${MAVEN_BASEDIR:-$(cd "$(dirname "$0")" && pwd)}"
WRAPPER_JAR="$MAVEN_PROJECTBASEDIR/.mvn/wrapper/maven-wrapper.jar"
WRAPPER_PROPERTIES="$MAVEN_PROJECTBASEDIR/.mvn/wrapper/maven-wrapper.properties"

# Download wrapper jar if missing
if [ ! -f "$WRAPPER_JAR" ]; then
    WRAPPER_URL=$(grep "wrapperUrl" "$WRAPPER_PROPERTIES" | cut -d'=' -f2-)
    echo "Downloading Maven Wrapper from $WRAPPER_URL"
    mkdir -p "$(dirname "$WRAPPER_JAR")"
    if command -v curl > /dev/null; then
        curl -fsSL -o "$WRAPPER_JAR" "$WRAPPER_URL"
    elif command -v wget > /dev/null; then
        wget -q -O "$WRAPPER_JAR" "$WRAPPER_URL"
    else
        echo "Error: curl or wget is required to download the Maven Wrapper"
        exit 1
    fi
fi

# Download Maven distribution if needed and run
DIST_URL=$(grep "distributionUrl" "$WRAPPER_PROPERTIES" | cut -d'=' -f2-)
MAVEN_HOME="$HOME/.m2/wrapper/dists/apache-maven-3.9.6"

if [ ! -d "$MAVEN_HOME" ]; then
    echo "Downloading Maven distribution..."
    mkdir -p "$MAVEN_HOME"
    ARCHIVE="/tmp/maven-dist-$$.zip"
    if command -v curl > /dev/null; then
        curl -fsSL -o "$ARCHIVE" "$DIST_URL"
    else
        wget -q -O "$ARCHIVE" "$DIST_URL"
    fi
    unzip -q -o "$ARCHIVE" -d "$MAVEN_HOME" 2>/dev/null || true
    rm -f "$ARCHIVE"
fi

# Find the actual Maven bin directory
MVN_BIN=$(find "$MAVEN_HOME" -name "mvn" -path "*/bin/mvn" 2>/dev/null | head -1)
if [ -z "$MVN_BIN" ]; then
    echo "Error: Could not find Maven binary in $MAVEN_HOME"
    exit 1
fi

exec "$MVN_BIN" "$@"
"""

DOCKERFILE_TEMPLATE = """FROM {base_image}
WORKDIR /app
COPY target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
"""


def check_java():
    """Check if Java is available and return version info."""
    try:
        result = subprocess.run(
            ["java", "-version"], capture_output=True, text=True, timeout=10
        )
        output = result.stderr or result.stdout  # java -version outputs to stderr
        version_line = output.strip().split('\n')[0] if output else "Unknown"
        return {"available": True, "version": version_line}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {
            "available": False,
            "version": None,
            "install_hint": "JDK 17+ required",
            "links": {
                "macOS": "brew install openjdk@17",
                "Ubuntu": "sudo apt install openjdk-17-jdk",
                "Windows": "https://adoptium.net/temurin/releases/",
                "Download": "https://adoptium.net/temurin/releases/"
            }
        }


def check_docker():
    """Check if Docker is available and return version info."""
    try:
        result = subprocess.run(
            ["docker", "--version"], capture_output=True, text=True, timeout=10
        )
        return {"available": True, "version": result.stdout.strip()}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {
            "available": False,
            "version": None,
            "install_hint": "Docker Desktop required for container builds",
            "links": {
                "macOS": "https://docs.docker.com/desktop/install/mac-install/",
                "Windows": "https://docs.docker.com/desktop/install/windows-install/",
                "Linux": "https://docs.docker.com/engine/install/",
                "Download": "https://www.docker.com/products/docker-desktop/"
            }
        }


def check_maven():
    """Check if Maven or Maven wrapper is available."""
    try:
        result = subprocess.run(
            ["mvn", "--version"], capture_output=True, text=True, timeout=10
        )
        version_line = result.stdout.strip().split('\n')[0] if result.stdout else ""
        return {"available": True, "version": version_line}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {
            "available": False,
            "version": None,
            "install_hint": "Maven 3.8+ required (or use built-in Maven Wrapper)",
            "links": {
                "macOS": "brew install maven",
                "Ubuntu": "sudo apt install maven",
                "Download": "https://maven.apache.org/download.cgi"
            }
        }


def prepare_project(files, project_name="migrated-app"):
    """Write generated files to a temp directory and set up Maven wrapper.

    Returns the path to the project directory.
    """
    base_dir = tempfile.mkdtemp(prefix="msb_build_")
    project_dir = os.path.join(base_dir, project_name)
    os.makedirs(project_dir, exist_ok=True)

    # Write all project files
    for filepath, content in files.items():
        full_path = os.path.join(project_dir, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)

    # Set up Maven wrapper
    mvn_wrapper_dir = os.path.join(project_dir, ".mvn", "wrapper")
    os.makedirs(mvn_wrapper_dir, exist_ok=True)

    with open(os.path.join(mvn_wrapper_dir, "maven-wrapper.properties"), 'w') as f:
        f.write(MAVEN_WRAPPER_PROPERTIES)

    mvnw_path = os.path.join(project_dir, "mvnw")
    with open(mvnw_path, 'w') as f:
        f.write(MVNW_SCRIPT)
    os.chmod(mvnw_path, 0o755)

    return project_dir


def _run_command(build_id, cmd, cwd, build_type="build"):
    """Run a command and store output lines in _builds."""
    build = _builds[build_id]
    build["status"] = "running"
    build["started_at"] = time.time()

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            bufsize=1,
            env={**os.environ, "JAVA_HOME": os.environ.get("JAVA_HOME", "")},
        )
        build["pid"] = process.pid

        for line in iter(process.stdout.readline, ""):
            build["output"].append(line.rstrip())

        process.wait()
        build["exit_code"] = process.returncode
        build["status"] = "success" if process.returncode == 0 else "failed"

    except Exception as e:
        build["output"].append(f"Error: {str(e)}")
        build["status"] = "failed"
        build["exit_code"] = -1

    build["finished_at"] = time.time()


def start_build(files, build_type="jar", project_name="migrated-app", docker_platform=None):
    """Start a build in a background thread.

    Returns a build_id that can be used to stream output.
    """
    build_id = str(uuid.uuid4())[:8]
    project_dir = prepare_project(files, project_name)

    build = {
        "id": build_id,
        "type": build_type,
        "status": "preparing",
        "output": [],
        "project_dir": project_dir,
        "artifact_path": None,
        "exit_code": None,
        "started_at": None,
        "finished_at": None,
        "pid": None,
    }
    _builds[build_id] = build

    if build_type == "jar":
        cmd = ["./mvnw", "clean", "package", "-DskipTests", "-B"]
        build["artifact_glob"] = os.path.join(project_dir, "target", "*.jar")

    elif build_type == "war":
        # Modify pom.xml for WAR packaging
        _modify_pom_for_war(project_dir)
        cmd = ["./mvnw", "clean", "package", "-DskipTests", "-B"]
        build["artifact_glob"] = os.path.join(project_dir, "target", "*.war")

    elif build_type == "docker":
        platform_config = DOCKER_PLATFORMS.get(docker_platform, DOCKER_PLATFORMS["linux-amd64"])
        _generate_dockerfile(project_dir, platform_config["base"])
        # Build JAR first, then Docker
        cmd = ["./mvnw", "clean", "package", "-DskipTests", "-B"]
        build["docker_platform"] = platform_config
        build["docker_image_name"] = f"{project_name}:latest"

    elif build_type == "test":
        cmd = ["./mvnw", "test", "-B"]

    else:
        build["status"] = "failed"
        build["output"].append(f"Unknown build type: {build_type}")
        return build_id

    # Use system Maven if mvnw doesn't work
    maven_check = check_maven()
    if maven_check["available"]:
        cmd[0] = "mvn"

    thread = threading.Thread(
        target=_run_build_pipeline,
        args=(build_id, cmd, project_dir, build_type),
        daemon=True,
    )
    thread.start()

    return build_id


def _run_build_pipeline(build_id, cmd, project_dir, build_type):
    """Run the full build pipeline."""
    build = _builds[build_id]
    build["status"] = "running"
    build["started_at"] = time.time()

    try:
        # Run Maven build
        build["output"].append(f">>> Starting {build_type} build...")
        build["output"].append(f">>> Working directory: {project_dir}")
        build["output"].append("")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_dir,
            bufsize=1,
        )
        build["pid"] = process.pid

        for line in iter(process.stdout.readline, ""):
            build["output"].append(line.rstrip())

        process.wait()

        if process.returncode != 0:
            build["exit_code"] = process.returncode
            build["status"] = "failed"
            build["finished_at"] = time.time()
            return

        # For Docker builds, run docker build after Maven
        if build_type == "docker" and build.get("docker_platform"):
            platform = build["docker_platform"]
            image_name = build["docker_image_name"]

            build["output"].append("")
            build["output"].append(f">>> Maven build successful. Building Docker image...")
            build["output"].append(f">>> Platform: {platform['label']} ({platform['platform']})")
            build["output"].append("")

            docker_cmd = [
                "docker", "build",
                "--platform", platform["platform"],
                "-t", image_name,
                project_dir,
            ]

            docker_proc = subprocess.Popen(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=project_dir,
                bufsize=1,
            )

            for line in iter(docker_proc.stdout.readline, ""):
                build["output"].append(line.rstrip())

            docker_proc.wait()

            if docker_proc.returncode != 0:
                build["exit_code"] = docker_proc.returncode
                build["status"] = "failed"
                build["finished_at"] = time.time()
                return

        # Find artifact
        import glob
        artifact_pattern = build.get("artifact_glob", "")
        if artifact_pattern:
            artifacts = glob.glob(artifact_pattern)
            # Filter out sources/javadoc jars
            artifacts = [a for a in artifacts if not any(
                s in a for s in ["-sources", "-javadoc", "original-"]
            )]
            if artifacts:
                build["artifact_path"] = artifacts[0]

        build["exit_code"] = 0
        build["status"] = "success"

    except Exception as e:
        build["output"].append(f"Error: {str(e)}")
        build["status"] = "failed"
        build["exit_code"] = -1

    build["finished_at"] = time.time()


def get_build(build_id):
    """Get build info."""
    return _builds.get(build_id)


def get_build_output(build_id, from_line=0):
    """Get build output starting from a line number."""
    build = _builds.get(build_id)
    if not build:
        return None
    return {
        "id": build["id"],
        "type": build["type"],
        "status": build["status"],
        "lines": build["output"][from_line:],
        "total_lines": len(build["output"]),
        "exit_code": build["exit_code"],
        "artifact_path": build.get("artifact_path"),
    }


def cleanup_build(build_id):
    """Clean up build temp directory."""
    build = _builds.get(build_id)
    if build and build.get("project_dir"):
        try:
            shutil.rmtree(os.path.dirname(build["project_dir"]), ignore_errors=True)
        except Exception:
            pass
    if build_id in _builds:
        del _builds[build_id]


def _modify_pom_for_war(project_dir):
    """Modify pom.xml to produce WAR packaging."""
    pom_path = os.path.join(project_dir, "pom.xml")
    if not os.path.exists(pom_path):
        return

    with open(pom_path, 'r') as f:
        content = f.read()

    # Change packaging to war
    if "<packaging>" in content:
        content = content.replace("<packaging>jar</packaging>", "<packaging>war</packaging>")
    else:
        content = content.replace(
            "</artifactId>",
            "</artifactId>\n    <packaging>war</packaging>",
            1,
        )

    # Add tomcat provided scope
    tomcat_dep = """
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-tomcat</artifactId>
            <scope>provided</scope>
        </dependency>"""

    if "spring-boot-starter-tomcat" not in content:
        content = content.replace("</dependencies>", tomcat_dep + "\n    </dependencies>")

    with open(pom_path, 'w') as f:
        f.write(content)


def _generate_dockerfile(project_dir, base_image):
    """Generate a Dockerfile in the project directory."""
    dockerfile_path = os.path.join(project_dir, "Dockerfile")
    with open(dockerfile_path, 'w') as f:
        f.write(DOCKERFILE_TEMPLATE.format(base_image=base_image))
