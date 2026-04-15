"""
Tests for generated Spring Boot Controller Java code — validates
@RestController, @RequestMapping, HTTP method annotations, @PathVariable,
@RequestBody, OpenAPI annotations, logger usage, and service injection.
"""

from __future__ import annotations

import re
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


# ── Helpers ──────────────────────────────────────────────────────

def _run_full_generation(mule_xml: str, group_id="com.example",
                         artifact_id="migrated-app") -> dict:
    """Parse Mule XML → convert → generate Spring Boot project. Returns files dict."""
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


def _get_controller_files(files: dict) -> dict:
    return {k: v for k, v in files.items() if "Controller.java" in k}


SIMPLE_GET_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http">
    <http:listener-config name="HTTP_Config" host="0.0.0.0" port="8081"/>
    <flow name="get-users-flow">
        <http:listener config-ref="HTTP_Config" path="/users" method="GET"/>
        <logger level="INFO" message="Fetching all users"/>
        <set-payload value='[{"id":1,"name":"John"}]'/>
    </flow>
</mule>"""

CRUD_API_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http"
      xmlns:db="http://www.mulesoft.org/schema/mule/db">
    <http:listener-config name="HTTP_Config" host="0.0.0.0" port="8081"/>
    <db:config name="DB_Config">
        <db:my-sql-connection host="localhost" port="3306" database="testdb"
                              user="root" password="pass"/>
    </db:config>
    <flow name="get-users">
        <http:listener config-ref="HTTP_Config" path="/api/users" method="GET"/>
        <logger level="INFO" message="GET /users"/>
    </flow>
    <flow name="get-user-by-id">
        <http:listener config-ref="HTTP_Config" path="/api/users/{id}" method="GET"/>
        <logger level="INFO" message="GET /users/:id"/>
    </flow>
    <flow name="create-user">
        <http:listener config-ref="HTTP_Config" path="/api/users" method="POST"/>
        <logger level="INFO" message="POST /users"/>
    </flow>
    <flow name="update-user">
        <http:listener config-ref="HTTP_Config" path="/api/users/{id}" method="PUT"/>
        <logger level="INFO" message="PUT /users/:id"/>
    </flow>
    <flow name="delete-user">
        <http:listener config-ref="HTTP_Config" path="/api/users/{id}" method="DELETE"/>
        <logger level="INFO" message="DELETE /users/:id"/>
    </flow>
</mule>"""


# ═══════════════════════════════════════════════════════════════════
#  Controller Class Structure
# ═══════════════════════════════════════════════════════════════════

class TestControllerStructure:
    def test_rest_controller_annotation(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        assert len(controllers) >= 1
        for content in controllers.values():
            assert "@RestController" in content

    def test_request_mapping_base_path(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        for content in controllers.values():
            assert "@RequestMapping" in content

    def test_package_declaration(self):
        files = _run_full_generation(SIMPLE_GET_XML, group_id="com.myorg")
        controllers = _get_controller_files(files)
        for content in controllers.values():
            assert "package com.myorg" in content

    def test_class_declaration(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        for content in controllers.values():
            assert "public class" in content

    def test_slf4j_logger(self):
        """Generated controllers should use @Slf4j or manual logger."""
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        for content in controllers.values():
            assert "@Slf4j" in content or "LoggerFactory" in content or "log." in content

    def test_import_statements_present(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        for content in controllers.values():
            assert "import " in content


# ═══════════════════════════════════════════════════════════════════
#  HTTP Method Annotations
# ═══════════════════════════════════════════════════════════════════

class TestHTTPMethodAnnotations:
    def test_get_mapping_generated(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        all_content = " ".join(controllers.values())
        assert "@GetMapping" in all_content

    def test_crud_all_methods(self):
        files = _run_full_generation(CRUD_API_XML)
        controllers = _get_controller_files(files)
        all_content = " ".join(controllers.values())
        assert "@GetMapping" in all_content
        assert "@PostMapping" in all_content
        assert "@PutMapping" in all_content
        assert "@DeleteMapping" in all_content

    def test_path_in_mapping_annotation(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        all_content = " ".join(controllers.values())
        # The path /users should appear in a mapping annotation
        assert "/users" in all_content

    def test_path_variable_for_id_endpoints(self):
        files = _run_full_generation(CRUD_API_XML)
        controllers = _get_controller_files(files)
        all_content = " ".join(controllers.values())
        assert "{id}" in all_content or "@PathVariable" in all_content


# ═══════════════════════════════════════════════════════════════════
#  OpenAPI / Swagger Annotations
# ═══════════════════════════════════════════════════════════════════

class TestOpenAPIAnnotations:
    def test_tag_annotation(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        all_content = " ".join(controllers.values())
        assert "@Tag(" in all_content

    def test_operation_annotation(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        all_content = " ".join(controllers.values())
        assert "@Operation(" in all_content

    def test_api_response_annotation(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        all_content = " ".join(controllers.values())
        assert "@ApiResponse(" in all_content

    def test_swagger_imports(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        all_content = " ".join(controllers.values())
        assert "import io.swagger.v3.oas.annotations.Operation;" in all_content
        assert "import io.swagger.v3.oas.annotations.tags.Tag;" in all_content


# ═══════════════════════════════════════════════════════════════════
#  Controller placed in correct package path
# ═══════════════════════════════════════════════════════════════════

class TestControllerFilePath:
    def test_controller_under_java_src(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        for path in controllers:
            assert path.startswith("src/main/java/")

    def test_controller_in_package_path(self):
        files = _run_full_generation(SIMPLE_GET_XML, group_id="com.example")
        controllers = _get_controller_files(files)
        for path in controllers:
            assert "com/example/" in path

    def test_controller_in_controller_subpackage(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        for path in controllers:
            assert "/controller/" in path


# ═══════════════════════════════════════════════════════════════════
#  Multiple Flows → Grouped Controllers
# ═══════════════════════════════════════════════════════════════════

class TestControllerGrouping:
    def test_same_config_ref_same_controller(self):
        """Flows sharing the same HTTP config-ref should be in one controller."""
        files = _run_full_generation(CRUD_API_XML)
        controllers = _get_controller_files(files)
        # All 5 CRUD flows share HTTP_Config → should be 1 controller
        assert len(controllers) == 1

    def test_all_endpoints_in_single_controller(self):
        files = _run_full_generation(CRUD_API_XML)
        controllers = _get_controller_files(files)
        content = list(controllers.values())[0]
        # Should have GET, POST, PUT, DELETE methods
        mapping_count = content.count("Mapping(") + content.count("Mapping\"")
        assert mapping_count >= 4  # At least GET, POST, PUT, DELETE


# ═══════════════════════════════════════════════════════════════════
#  Generated Controller Method Bodies
# ═══════════════════════════════════════════════════════════════════

class TestControllerMethodBodies:
    def test_logger_statement_present(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        all_content = " ".join(controllers.values())
        # Should have translated MuleSoft logger to Java log statement
        assert "log.info(" in all_content or "log.debug(" in all_content or \
               "log.warn(" in all_content or "log.error(" in all_content

    def test_return_statement_present(self):
        files = _run_full_generation(SIMPLE_GET_XML)
        controllers = _get_controller_files(files)
        all_content = " ".join(controllers.values())
        assert "return " in all_content or "ResponseEntity" in all_content


# ═══════════════════════════════════════════════════════════════════
#  Scheduler, JMS, Kafka Listeners
# ═══════════════════════════════════════════════════════════════════

SCHEDULER_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core">
    <flow name="daily-cleanup">
        <scheduler>
            <scheduling-strategy>
                <fixed-frequency frequency="86400000"/>
            </scheduling-strategy>
        </scheduler>
        <logger level="INFO" message="Running cleanup"/>
    </flow>
</mule>"""

JMS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:jms="http://www.mulesoft.org/schema/mule/jms">
    <jms:config name="JMS_Config"/>
    <flow name="order-processor">
        <jms:listener config-ref="JMS_Config" destination="orders.queue"/>
        <logger level="INFO" message="Processing order"/>
    </flow>
</mule>"""

KAFKA_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:kafka="http://www.mulesoft.org/schema/mule/kafka">
    <kafka:consumer-config name="Kafka_Config"/>
    <flow name="event-consumer">
        <kafka:consumer config-ref="Kafka_Config" topic="events"/>
        <logger level="INFO" message="Consuming event"/>
    </flow>
</mule>"""


class TestSchedulerGeneration:
    def test_scheduled_annotation(self):
        files = _run_full_generation(SCHEDULER_XML)
        sched_files = {k: v for k, v in files.items()
                       if "Scheduled" in k or "scheduler" in k.lower()}
        assert len(sched_files) >= 1
        content = " ".join(sched_files.values())
        assert "@Scheduled" in content

    def test_scheduled_has_component_or_config(self):
        files = _run_full_generation(SCHEDULER_XML)
        sched_files = {k: v for k, v in files.items()
                       if "Scheduled" in k or "scheduler" in k.lower()}
        content = " ".join(sched_files.values())
        assert "@Component" in content or "@Configuration" in content or "@Service" in content


class TestJmsListenerGeneration:
    def test_jms_listener_annotation(self):
        files = _run_full_generation(JMS_XML)
        jms_files = {k: v for k, v in files.items() if "Jms" in k or "jms" in k.lower()}
        assert len(jms_files) >= 1
        content = " ".join(jms_files.values())
        assert "@JmsListener" in content

    def test_jms_destination(self):
        files = _run_full_generation(JMS_XML)
        jms_files = {k: v for k, v in files.items() if "Jms" in k or "jms" in k.lower()}
        content = " ".join(jms_files.values())
        assert "orders.queue" in content


class TestKafkaListenerGeneration:
    def test_kafka_listener_annotation(self):
        files = _run_full_generation(KAFKA_XML)
        kafka_files = {k: v for k, v in files.items() if "Kafka" in k or "kafka" in k.lower()}
        assert len(kafka_files) >= 1
        content = " ".join(kafka_files.values())
        assert "@KafkaListener" in content

    def test_kafka_topic(self):
        files = _run_full_generation(KAFKA_XML)
        kafka_files = {k: v for k, v in files.items() if "Kafka" in k or "kafka" in k.lower()}
        content = " ".join(kafka_files.values())
        assert "events" in content


# ═══════════════════════════════════════════════════════════════════
#  Sub-flow → Service Class
# ═══════════════════════════════════════════════════════════════════

SUBFLOW_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http">
    <http:listener-config name="HTTP_Config" host="0.0.0.0" port="8081"/>
    <flow name="main-flow">
        <http:listener config-ref="HTTP_Config" path="/api" method="GET"/>
        <flow-ref name="validate-request"/>
    </flow>
    <sub-flow name="validate-request">
        <logger level="INFO" message="Validating request"/>
    </sub-flow>
</mule>"""


class TestSubFlowToService:
    def test_service_class_generated(self):
        files = _run_full_generation(SUBFLOW_XML)
        service_files = {k: v for k, v in files.items()
                         if "Service.java" in k and "service/" in k}
        assert len(service_files) >= 1

    def test_service_annotation(self):
        files = _run_full_generation(SUBFLOW_XML)
        service_files = {k: v for k, v in files.items()
                         if "Service.java" in k and "service/" in k}
        content = " ".join(service_files.values())
        assert "@Service" in content or "@Component" in content
