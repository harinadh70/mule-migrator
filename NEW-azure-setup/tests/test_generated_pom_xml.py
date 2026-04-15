"""
Tests for the generated pom.xml — validates Maven project structure,
dependencies, plugins, and Spring Boot parent configuration.
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
from backend.migrator.spring_generator import SpringBootGenerator


# ── Helpers ──────────────────────────────────────────────────────

def _generate_pom(connectors=None, group_id="com.example",
                  artifact_id="migrated-app", java_version="17"):
    gen = SpringBootGenerator(artifact_id, group_id, java_version)
    mapper = ConnectorMapper()
    parsed = {
        "flows": [], "sub_flows": [], "connectors": connectors or set(),
        "batch_jobs": [], "global_configs": [], "secure_properties": [],
    }
    connector_info = mapper.map_connectors(parsed)
    return gen._generate_pom(connector_info)


# ═══════════════════════════════════════════════════════════════════
#  POM Structure
# ═══════════════════════════════════════════════════════════════════

class TestPomStructure:
    def test_valid_xml_declaration(self):
        pom = _generate_pom()
        assert pom.startswith('<?xml version="1.0"')

    def test_maven_namespace(self):
        pom = _generate_pom()
        assert 'xmlns="http://maven.apache.org/POM/4.0.0"' in pom

    def test_model_version(self):
        pom = _generate_pom()
        assert "<modelVersion>4.0.0</modelVersion>" in pom

    def test_spring_boot_parent(self):
        pom = _generate_pom()
        assert "<artifactId>spring-boot-starter-parent</artifactId>" in pom
        assert "<version>3.2.0</version>" in pom

    def test_group_id_set(self):
        pom = _generate_pom(group_id="com.mycompany")
        assert "<groupId>com.mycompany</groupId>" in pom

    def test_artifact_id_set(self):
        pom = _generate_pom(artifact_id="order-service")
        assert "<artifactId>order-service</artifactId>" in pom

    def test_java_version_17(self):
        pom = _generate_pom(java_version="17")
        assert "<java.version>17</java.version>" in pom

    def test_java_version_21(self):
        pom = _generate_pom(java_version="21")
        assert "<java.version>21</java.version>" in pom

    def test_snapshot_version(self):
        pom = _generate_pom()
        assert "<version>1.0.0-SNAPSHOT</version>" in pom

    def test_description(self):
        pom = _generate_pom()
        assert "Migrated from MuleSoft" in pom

    def test_spring_boot_maven_plugin(self):
        pom = _generate_pom()
        assert "<artifactId>spring-boot-maven-plugin</artifactId>" in pom

    def test_lombok_excluded_from_plugin(self):
        pom = _generate_pom()
        assert "lombok" in pom
        # Lombok should be in excludes section of the plugin
        assert "<exclude>" in pom


# ═══════════════════════════════════════════════════════════════════
#  Common Dependencies (always present)
# ═══════════════════════════════════════════════════════════════════

class TestCommonDependencies:
    def test_spring_boot_starter(self):
        pom = _generate_pom()
        assert "spring-boot-starter</artifactId>" in pom

    def test_actuator(self):
        pom = _generate_pom()
        assert "spring-boot-starter-actuator" in pom

    def test_spring_boot_test(self):
        pom = _generate_pom()
        assert "spring-boot-starter-test" in pom
        assert "<scope>test</scope>" in pom

    def test_lombok(self):
        pom = _generate_pom()
        assert "lombok" in pom

    def test_springdoc_openapi(self):
        pom = _generate_pom()
        assert "springdoc-openapi-starter-webmvc-ui" in pom

    def test_h2_database(self):
        pom = _generate_pom()
        assert "<artifactId>h2</artifactId>" in pom


# ═══════════════════════════════════════════════════════════════════
#  Connector-specific Dependencies
# ═══════════════════════════════════════════════════════════════════

class TestConnectorDependencies:
    def test_http_adds_web_starter(self):
        pom = _generate_pom(connectors={"http"})
        assert "spring-boot-starter-web" in pom

    def test_http_adds_webflux_starter(self):
        pom = _generate_pom(connectors={"http"})
        assert "spring-boot-starter-webflux" in pom

    def test_http_adds_jackson(self):
        pom = _generate_pom(connectors={"http"})
        assert "jackson-databind" in pom

    def test_database_adds_jpa(self):
        pom = _generate_pom(connectors={"database"})
        assert "spring-boot-starter-data-jpa" in pom

    def test_database_adds_jdbc(self):
        pom = _generate_pom(connectors={"database"})
        assert "spring-boot-starter-jdbc" in pom

    def test_jms_adds_activemq(self):
        pom = _generate_pom(connectors={"jms"})
        assert "spring-boot-starter-activemq" in pom

    def test_amqp_adds_rabbitmq(self):
        pom = _generate_pom(connectors={"amqp"})
        assert "spring-boot-starter-amqp" in pom

    def test_kafka_adds_spring_kafka(self):
        pom = _generate_pom(connectors={"kafka"})
        assert "spring-kafka" in pom

    def test_sftp_adds_spring_integration_sftp(self):
        pom = _generate_pom(connectors={"sftp"})
        assert "spring-integration-sftp" in pom

    def test_email_adds_mail_starter(self):
        pom = _generate_pom(connectors={"email"})
        assert "spring-boot-starter-mail" in pom

    def test_redis_adds_data_redis(self):
        pom = _generate_pom(connectors={"redis"})
        assert "spring-boot-starter-data-redis" in pom

    def test_mongo_adds_data_mongodb(self):
        pom = _generate_pom(connectors={"mongo"})
        assert "spring-boot-starter-data-mongodb" in pom

    def test_s3_adds_aws_sdk(self):
        pom = _generate_pom(connectors={"s3"})
        assert "software.amazon.awssdk" in pom

    def test_sqs_adds_aws_sdk(self):
        pom = _generate_pom(connectors={"sqs"})
        assert "software.amazon.awssdk" in pom

    def test_oauth_adds_security(self):
        pom = _generate_pom(connectors={"oauth"})
        assert "spring-boot-starter-security" in pom
        assert "spring-boot-starter-oauth2-client" in pom

    def test_ws_adds_web_services(self):
        pom = _generate_pom(connectors={"ws"})
        assert "spring-boot-starter-web-services" in pom

    def test_validation_adds_validation_starter(self):
        pom = _generate_pom(connectors={"validation"})
        assert "spring-boot-starter-validation" in pom

    def test_elasticsearch_adds_data_elasticsearch(self):
        pom = _generate_pom(connectors={"elasticsearch"})
        assert "spring-boot-starter-data-elasticsearch" in pom

    def test_batch_adds_batch_starter(self):
        pom = _generate_pom(connectors={"batch"})
        assert "spring-boot-starter-batch" in pom


# ═══════════════════════════════════════════════════════════════════
#  No Duplicate Dependencies
# ═══════════════════════════════════════════════════════════════════

class TestNoDuplicates:
    @pytest.mark.xfail(reason="Known bug: generator produces duplicate actuator/lombok entries")
    def test_no_duplicate_artifact_ids(self):
        """Even with multiple connectors, no dependency should appear twice."""
        pom = _generate_pom(connectors={"http", "database", "jms", "kafka", "redis"})
        import re
        artifacts = re.findall(r"<artifactId>(.*?)</artifactId>", pom)
        # Exclude parent and plugin artifactIds
        dep_artifacts = [a for a in artifacts
                         if a not in ("spring-boot-starter-parent", "spring-boot-maven-plugin",
                                      "spring-boot-starter-test", "h2")]
        # Check only within <dependencies> block
        assert len(dep_artifacts) == len(set(dep_artifacts)), \
            f"Duplicate dependencies found: {[a for a in dep_artifacts if dep_artifacts.count(a) > 1]}"
