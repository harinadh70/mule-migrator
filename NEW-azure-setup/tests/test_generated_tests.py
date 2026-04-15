"""
Tests for generated test classes — validates that the migrator produces
correct @SpringBootTest, @WebMvcTest, and integration test Java files
with proper MockMvc setup, @MockBean annotations, and test method structure.
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


CRUD_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http">
    <http:listener-config name="HTTP_Config" host="0.0.0.0" port="8081"/>
    <flow name="get-users">
        <http:listener config-ref="HTTP_Config" path="/api/users" method="GET"/>
        <logger level="INFO" message="GET users"/>
    </flow>
    <flow name="get-user-by-id">
        <http:listener config-ref="HTTP_Config" path="/api/users/{id}" method="GET"/>
        <logger level="INFO" message="GET user by id"/>
    </flow>
    <flow name="create-user">
        <http:listener config-ref="HTTP_Config" path="/api/users" method="POST"/>
        <logger level="INFO" message="POST user"/>
    </flow>
    <flow name="update-user">
        <http:listener config-ref="HTTP_Config" path="/api/users/{id}" method="PUT"/>
        <logger level="INFO" message="PUT user"/>
    </flow>
    <flow name="delete-user">
        <http:listener config-ref="HTTP_Config" path="/api/users/{id}" method="DELETE"/>
        <logger level="INFO" message="DELETE user"/>
    </flow>
</mule>"""


# ═══════════════════════════════════════════════════════════════════
#  Application Context Test (@SpringBootTest)
# ═══════════════════════════════════════════════════════════════════

class TestApplicationContextTests:
    def test_generated(self):
        files = _full_generate(CRUD_XML)
        test_files = {k: v for k, v in files.items() if "Tests.java" in k and "src/test/" in k}
        assert len(test_files) >= 1

    def test_spring_boot_test_annotation(self):
        files = _full_generate(CRUD_XML)
        test_files = {k: v for k, v in files.items()
                      if "Tests.java" in k and "src/test/" in k
                      and "Controller" not in k and "Integration" not in k}
        for content in test_files.values():
            assert "@SpringBootTest" in content

    def test_context_loads_test(self):
        files = _full_generate(CRUD_XML)
        test_files = {k: v for k, v in files.items()
                      if "Tests.java" in k and "src/test/" in k
                      and "Controller" not in k and "Integration" not in k}
        for content in test_files.values():
            assert "contextLoads" in content

    def test_assert_not_null(self):
        files = _full_generate(CRUD_XML)
        test_files = {k: v for k, v in files.items()
                      if "Tests.java" in k and "src/test/" in k
                      and "Controller" not in k and "Integration" not in k}
        for content in test_files.values():
            assert "assertNotNull" in content

    def test_display_name_annotation(self):
        files = _full_generate(CRUD_XML)
        test_files = {k: v for k, v in files.items()
                      if "Tests.java" in k and "src/test/" in k
                      and "Controller" not in k and "Integration" not in k}
        for content in test_files.values():
            assert "@DisplayName" in content

    def test_junit5_imports(self):
        files = _full_generate(CRUD_XML)
        test_files = {k: v for k, v in files.items()
                      if "Tests.java" in k and "src/test/" in k
                      and "Controller" not in k and "Integration" not in k}
        for content in test_files.values():
            assert "import org.junit.jupiter.api.Test;" in content

    def test_main_method_test(self):
        files = _full_generate(CRUD_XML)
        test_files = {k: v for k, v in files.items()
                      if "Tests.java" in k and "src/test/" in k
                      and "Controller" not in k and "Integration" not in k}
        for content in test_files.values():
            assert "mainMethodRuns" in content or "main(" in content


# ═══════════════════════════════════════════════════════════════════
#  Controller Unit Tests (@WebMvcTest)
# ═══════════════════════════════════════════════════════════════════

class TestControllerUnitTests:
    def test_generated(self):
        files = _full_generate(CRUD_XML)
        unit_test_files = {k: v for k, v in files.items()
                           if "ControllerTest.java" in k and "Integration" not in k}
        assert len(unit_test_files) >= 1

    def test_webmvc_test_annotation(self):
        files = _full_generate(CRUD_XML)
        unit_test_files = {k: v for k, v in files.items()
                           if "ControllerTest.java" in k and "Integration" not in k}
        for content in unit_test_files.values():
            assert "@WebMvcTest" in content

    def test_mock_mvc_injected(self):
        files = _full_generate(CRUD_XML)
        unit_test_files = {k: v for k, v in files.items()
                           if "ControllerTest.java" in k and "Integration" not in k}
        for content in unit_test_files.values():
            assert "MockMvc" in content
            assert "@Autowired" in content

    def test_get_endpoint_test(self):
        files = _full_generate(CRUD_XML)
        unit_test_files = {k: v for k, v in files.items()
                           if "ControllerTest.java" in k and "Integration" not in k}
        all_content = " ".join(unit_test_files.values())
        assert "get(" in all_content
        assert "status().isOk()" in all_content

    def test_post_endpoint_test(self):
        files = _full_generate(CRUD_XML)
        unit_test_files = {k: v for k, v in files.items()
                           if "ControllerTest.java" in k and "Integration" not in k}
        all_content = " ".join(unit_test_files.values())
        assert "post(" in all_content

    def test_put_endpoint_test(self):
        files = _full_generate(CRUD_XML)
        unit_test_files = {k: v for k, v in files.items()
                           if "ControllerTest.java" in k and "Integration" not in k}
        all_content = " ".join(unit_test_files.values())
        assert "put(" in all_content

    def test_delete_endpoint_test(self):
        files = _full_generate(CRUD_XML)
        unit_test_files = {k: v for k, v in files.items()
                           if "ControllerTest.java" in k and "Integration" not in k}
        all_content = " ".join(unit_test_files.values())
        assert "delete(" in all_content

    def test_content_type_json(self):
        files = _full_generate(CRUD_XML)
        unit_test_files = {k: v for k, v in files.items()
                           if "ControllerTest.java" in k and "Integration" not in k}
        all_content = " ".join(unit_test_files.values())
        assert "MediaType.APPLICATION_JSON" in all_content

    def test_display_names(self):
        files = _full_generate(CRUD_XML)
        unit_test_files = {k: v for k, v in files.items()
                           if "ControllerTest.java" in k and "Integration" not in k}
        for content in unit_test_files.values():
            assert "@DisplayName" in content

    def test_unknown_path_404_test(self):
        files = _full_generate(CRUD_XML)
        unit_test_files = {k: v for k, v in files.items()
                           if "ControllerTest.java" in k and "Integration" not in k}
        all_content = " ".join(unit_test_files.values())
        assert "isNotFound()" in all_content

    def test_mock_mvc_static_imports(self):
        files = _full_generate(CRUD_XML)
        unit_test_files = {k: v for k, v in files.items()
                           if "ControllerTest.java" in k and "Integration" not in k}
        for content in unit_test_files.values():
            assert "import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;" in content
            assert "import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;" in content


# ═══════════════════════════════════════════════════════════════════
#  Controller Integration Tests (@SpringBootTest)
# ═══════════════════════════════════════════════════════════════════

class TestControllerIntegrationTests:
    def test_generated(self):
        files = _full_generate(CRUD_XML)
        int_test_files = {k: v for k, v in files.items()
                          if "IntegrationTest.java" in k}
        assert len(int_test_files) >= 1

    def test_spring_boot_test_annotation(self):
        files = _full_generate(CRUD_XML)
        int_test_files = {k: v for k, v in files.items()
                          if "IntegrationTest.java" in k}
        for content in int_test_files.values():
            assert "@SpringBootTest" in content

    def test_auto_configure_mock_mvc(self):
        files = _full_generate(CRUD_XML)
        int_test_files = {k: v for k, v in files.items()
                          if "IntegrationTest.java" in k}
        for content in int_test_files.values():
            assert "@AutoConfigureMockMvc" in content

    def test_full_crud_flow_test(self):
        files = _full_generate(CRUD_XML)
        int_test_files = {k: v for k, v in files.items()
                          if "IntegrationTest.java" in k}
        all_content = " ".join(int_test_files.values())
        assert "Full CRUD flow" in all_content or "testFullCrudFlow" in all_content

    def test_concurrent_requests_test(self):
        files = _full_generate(CRUD_XML)
        int_test_files = {k: v for k, v in files.items()
                          if "IntegrationTest.java" in k}
        all_content = " ".join(int_test_files.values())
        assert "Concurrent" in all_content or "concurrent" in all_content


# ═══════════════════════════════════════════════════════════════════
#  Test Files Under Correct Path
# ═══════════════════════════════════════════════════════════════════

class TestFilePaths:
    def test_unit_tests_under_src_test(self):
        files = _full_generate(CRUD_XML)
        test_files = {k for k in files if "Test.java" in k or "Tests.java" in k}
        for path in test_files:
            assert "src/test/java/" in path

    def test_test_package_matches_source(self):
        files = _full_generate(CRUD_XML, group_id="com.myorg")
        test_files = {k for k in files if "Test.java" in k or "Tests.java" in k}
        for path in test_files:
            assert "com/myorg/" in path


# ═══════════════════════════════════════════════════════════════════
#  Edge Case — No Controllers → No Controller Tests
# ═══════════════════════════════════════════════════════════════════

class TestNoControllerNoTests:
    def test_no_controller_tests_when_no_http_flows(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core">
    <flow name="scheduled-job">
        <scheduler>
            <scheduling-strategy>
                <fixed-frequency frequency="60000"/>
            </scheduling-strategy>
        </scheduler>
        <logger level="INFO" message="tick"/>
    </flow>
</mule>"""
        files = _full_generate(xml)
        controller_tests = {k for k in files if "ControllerTest.java" in k}
        # No HTTP flows → no controller tests
        assert len(controller_tests) == 0
