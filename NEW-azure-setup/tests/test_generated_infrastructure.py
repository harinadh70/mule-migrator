"""
Tests for generated infrastructure files — validates Dockerfile,
docker-compose.yml, .gitignore, application.properties, application.yml,
profile-specific properties, logback-spring.xml, and JsonUtil.java.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
_OLD_SETUP = str(Path(_PROJECT_ROOT) / "OLD-local-setup")
for p in (_PROJECT_ROOT, _OLD_SETUP):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.migrator.connector_mapper import ConnectorMapper
from backend.migrator.dataweave_converter import DataWeaveConverter
from backend.migrator.flow_converter import FlowConverter
from backend.migrator.spring_generator import SpringBootGenerator


@pytest.fixture
def gen():
    return SpringBootGenerator("test-app", "com.example", "17")


def _full_generate(mule_xml, group_id="com.example", artifact_id="test-app"):
    from backend.migrator.parser import MuleSoftParser
    parser = MuleSoftParser()
    parsed = parser.parse(mule_xml)
    dw = DataWeaveConverter()
    mapper = ConnectorMapper()
    converter = FlowConverter(dw, mapper)
    spring_files = converter.convert(parsed, {})
    connector_info = mapper.map_connectors(parsed)
    gen = SpringBootGenerator(artifact_id, group_id)
    return gen.generate(spring_files, connector_info, parsed)


BASIC_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http">
    <http:listener-config name="HTTP_Config" host="0.0.0.0" port="8081"/>
    <flow name="hello-flow">
        <http:listener config-ref="HTTP_Config" path="/hello" method="GET"/>
        <set-payload value="Hello"/>
    </flow>
</mule>"""


# ═══════════════════════════════════════════════════════════════════
#  Dockerfile
# ═══════════════════════════════════════════════════════════════════

class TestDockerfile:
    def test_generated(self):
        files = _full_generate(BASIC_XML)
        assert "Dockerfile" in files

    def test_multi_stage_build(self):
        files = _full_generate(BASIC_XML)
        df = files["Dockerfile"]
        assert "AS build" in df
        assert "COPY --from=build" in df

    def test_java_version_in_base_image(self):
        files = _full_generate(BASIC_XML)
        df = files["Dockerfile"]
        assert "eclipse-temurin:17" in df

    def test_java_21_in_base_image(self):
        from backend.migrator.parser import MuleSoftParser
        parser = MuleSoftParser()
        parsed = parser.parse(BASIC_XML)
        mapper = ConnectorMapper()
        dw = DataWeaveConverter()
        converter = FlowConverter(dw, mapper)
        spring_files = converter.convert(parsed, {})
        ci = mapper.map_connectors(parsed)
        gen = SpringBootGenerator("app", "com.test", "21")
        files = gen.generate(spring_files, ci, parsed)
        assert "eclipse-temurin:21" in files["Dockerfile"]

    def test_exposes_port_8080(self):
        files = _full_generate(BASIC_XML)
        assert "EXPOSE 8080" in files["Dockerfile"]

    def test_entrypoint(self):
        files = _full_generate(BASIC_XML)
        assert "java" in files["Dockerfile"]
        assert "app.jar" in files["Dockerfile"]

    def test_maven_build_step(self):
        files = _full_generate(BASIC_XML)
        assert "mvnw" in files["Dockerfile"] or "mvn" in files["Dockerfile"]
        assert "-DskipTests" in files["Dockerfile"]


# ═══════════════════════════════════════════════════════════════════
#  docker-compose.yml
# ═══════════════════════════════════════════════════════════════════

class TestDockerCompose:
    def test_generated(self):
        files = _full_generate(BASIC_XML)
        assert "docker-compose.yml" in files

    def test_has_app_service(self):
        files = _full_generate(BASIC_XML)
        dc = files["docker-compose.yml"]
        assert "app:" in dc
        assert "build: ." in dc

    def test_app_port_mapping(self):
        files = _full_generate(BASIC_XML)
        dc = files["docker-compose.yml"]
        assert "8080:8080" in dc

    def test_spring_profile_active(self):
        files = _full_generate(BASIC_XML)
        dc = files["docker-compose.yml"]
        assert "SPRING_PROFILES_ACTIVE" in dc

    def test_mysql_service_when_database(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:db="http://www.mulesoft.org/schema/mule/db">
    <db:config name="DB">
        <db:my-sql-connection host="localhost" port="3306" database="testdb"/>
    </db:config>
</mule>"""
        files = _full_generate(xml)
        dc = files["docker-compose.yml"]
        assert "mysql" in dc.lower() or "db:" in dc

    def test_redis_service_when_redis(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:os="http://www.mulesoft.org/schema/mule/os">
    <os:config name="OS"/>
</mule>"""
        files = _full_generate(xml)
        dc = files["docker-compose.yml"]
        assert "redis" in dc

    def test_kafka_service_when_kafka(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:kafka="http://www.mulesoft.org/schema/mule/kafka">
    <kafka:consumer-config name="K"/>
    <flow name="f">
        <kafka:consumer config-ref="K" topic="t"/>
    </flow>
</mule>"""
        files = _full_generate(xml)
        dc = files["docker-compose.yml"]
        assert "kafka" in dc
        assert "zookeeper" in dc


# ═══════════════════════════════════════════════════════════════════
#  .gitignore
# ═══════════════════════════════════════════════════════════════════

class TestGitignore:
    def test_generated(self):
        files = _full_generate(BASIC_XML)
        assert ".gitignore" in files

    def test_target_ignored(self):
        files = _full_generate(BASIC_XML)
        assert "target/" in files[".gitignore"]

    def test_idea_ignored(self):
        files = _full_generate(BASIC_XML)
        assert ".idea" in files[".gitignore"]

    def test_ds_store_ignored(self):
        files = _full_generate(BASIC_XML)
        assert ".DS_Store" in files[".gitignore"]

    def test_build_ignored(self):
        files = _full_generate(BASIC_XML)
        assert "build/" in files[".gitignore"]


# ═══════════════════════════════════════════════════════════════════
#  application.properties
# ═══════════════════════════════════════════════════════════════════

class TestApplicationProperties:
    def test_generated(self):
        files = _full_generate(BASIC_XML)
        assert "src/main/resources/application.properties" in files

    def test_app_name_set(self):
        files = _full_generate(BASIC_XML, artifact_id="my-service")
        props = files["src/main/resources/application.properties"]
        assert "spring.application.name=my-service" in props

    def test_logging_configured(self):
        files = _full_generate(BASIC_XML)
        props = files["src/main/resources/application.properties"]
        assert "logging.level.root=INFO" in props

    def test_actuator_endpoints(self):
        files = _full_generate(BASIC_XML)
        props = files["src/main/resources/application.properties"]
        assert "management.endpoints.web.exposure.include" in props
        assert "health" in props

    def test_http_port_from_listener(self):
        files = _full_generate(BASIC_XML)
        props = files["src/main/resources/application.properties"]
        assert "server.port=8081" in props

    def test_database_properties_when_db(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:db="http://www.mulesoft.org/schema/mule/db">
    <db:config name="DB">
        <db:my-sql-connection host="myhost" port="3306" database="mydb"
                              user="admin" password="secret"/>
    </db:config>
</mule>"""
        files = _full_generate(xml)
        props = files["src/main/resources/application.properties"]
        assert "spring.datasource.url" in props
        assert "spring.datasource.username=admin" in props


# ═══════════════════════════════════════════════════════════════════
#  application.yml
# ═══════════════════════════════════════════════════════════════════

class TestApplicationYml:
    def test_generated(self):
        files = _full_generate(BASIC_XML)
        assert "src/main/resources/application.yml" in files

    def test_app_name_in_yml(self):
        files = _full_generate(BASIC_XML, artifact_id="order-api")
        yml = files["src/main/resources/application.yml"]
        assert "name: order-api" in yml

    def test_server_port(self):
        files = _full_generate(BASIC_XML)
        yml = files["src/main/resources/application.yml"]
        assert "port: 8081" in yml

    def test_springdoc_swagger(self):
        files = _full_generate(BASIC_XML)
        yml = files["src/main/resources/application.yml"]
        assert "swagger-ui:" in yml
        assert "api-docs:" in yml

    def test_actuator_management(self):
        files = _full_generate(BASIC_XML)
        yml = files["src/main/resources/application.yml"]
        assert "management:" in yml
        assert "health" in yml


# ═══════════════════════════════════════════════════════════════════
#  Profile Properties
# ═══════════════════════════════════════════════════════════════════

class TestProfileProperties:
    def test_dev_profile_generated(self):
        files = _full_generate(BASIC_XML)
        assert "src/main/resources/application-dev.properties" in files

    def test_prod_profile_generated(self):
        files = _full_generate(BASIC_XML)
        assert "src/main/resources/application-prod.properties" in files

    def test_dev_debug_logging(self):
        files = _full_generate(BASIC_XML)
        dev = files["src/main/resources/application-dev.properties"]
        assert "logging.level.root=DEBUG" in dev

    def test_prod_warn_logging(self):
        files = _full_generate(BASIC_XML)
        prod = files["src/main/resources/application-prod.properties"]
        assert "logging.level.root=WARN" in prod

    def test_prod_no_stacktrace(self):
        files = _full_generate(BASIC_XML)
        prod = files["src/main/resources/application-prod.properties"]
        assert "server.error.include-stacktrace=never" in prod


# ═══════════════════════════════════════════════════════════════════
#  logback-spring.xml
# ═══════════════════════════════════════════════════════════════════

class TestLogbackConfig:
    def test_generated(self):
        files = _full_generate(BASIC_XML)
        assert "src/main/resources/logback-spring.xml" in files

    def test_console_appender(self):
        files = _full_generate(BASIC_XML)
        lb = files["src/main/resources/logback-spring.xml"]
        assert 'name="CONSOLE"' in lb

    def test_file_appender(self):
        files = _full_generate(BASIC_XML)
        lb = files["src/main/resources/logback-spring.xml"]
        assert 'name="FILE"' in lb
        assert "RollingFileAppender" in lb

    def test_dev_profile(self):
        files = _full_generate(BASIC_XML)
        lb = files["src/main/resources/logback-spring.xml"]
        assert '<springProfile name="dev">' in lb

    def test_prod_profile(self):
        files = _full_generate(BASIC_XML)
        lb = files["src/main/resources/logback-spring.xml"]
        assert '<springProfile name="prod">' in lb

    def test_group_id_logger(self):
        files = _full_generate(BASIC_XML, group_id="com.mycompany")
        lb = files["src/main/resources/logback-spring.xml"]
        assert 'name="com.mycompany"' in lb


# ═══════════════════════════════════════════════════════════════════
#  JsonUtil.java
# ═══════════════════════════════════════════════════════════════════

class TestJsonUtil:
    def test_generated(self):
        files = _full_generate(BASIC_XML)
        assert any("JsonUtil.java" in k for k in files)

    def test_package_declaration(self):
        files = _full_generate(BASIC_XML, group_id="com.example")
        util = [v for k, v in files.items() if "JsonUtil.java" in k][0]
        assert "package com.example.util;" in util

    def test_object_mapper(self):
        files = _full_generate(BASIC_XML)
        util = [v for k, v in files.items() if "JsonUtil.java" in k][0]
        assert "ObjectMapper" in util

    def test_to_json_method(self):
        files = _full_generate(BASIC_XML)
        util = [v for k, v in files.items() if "JsonUtil.java" in k][0]
        assert "toJson" in util
        assert "writeValueAsString" in util

    def test_from_json_method(self):
        files = _full_generate(BASIC_XML)
        util = [v for k, v in files.items() if "JsonUtil.java" in k][0]
        assert "fromJson" in util
        assert "readValue" in util

    def test_generic_from_json_method(self):
        files = _full_generate(BASIC_XML)
        util = [v for k, v in files.items() if "JsonUtil.java" in k][0]
        assert "Class<T> clazz" in util
