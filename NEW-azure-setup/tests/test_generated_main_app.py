"""
Tests for the generated Main Application Java class — validates
@SpringBootApplication annotations, conditional annotations like
@EnableScheduling, @EnableJms, @EnableCaching, imports, and class structure.
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

from backend.migrator.spring_generator import SpringBootGenerator


# ── Helpers ──────────────────────────────────────────────────────

def _generate_main_app(group_id="com.example", artifact_id="migrated-app",
                       parsed_data=None, connector_info=None):
    gen = SpringBootGenerator(artifact_id, group_id)
    app_class = gen._to_class_name(artifact_id) + "Application"
    pd = parsed_data or {"flows": [], "sub_flows": [], "batch_jobs": []}
    ci = connector_info or {"connectors": set(), "dependencies": []}
    return gen._generate_main_app(app_class, pd, ci)


# ═══════════════════════════════════════════════════════════════════
#  Class Structure
# ═══════════════════════════════════════════════════════════════════

class TestMainAppStructure:
    def test_package_declaration(self):
        code = _generate_main_app(group_id="com.mycompany")
        assert "package com.mycompany;" in code

    def test_spring_boot_application_annotation(self):
        code = _generate_main_app()
        assert "@SpringBootApplication" in code

    def test_class_name_from_artifact(self):
        code = _generate_main_app(artifact_id="order-service")
        assert "public class OrderServiceApplication" in code

    def test_main_method(self):
        code = _generate_main_app()
        assert "public static void main(String[] args)" in code
        assert "SpringApplication.run(" in code

    def test_main_method_passes_class(self):
        code = _generate_main_app(artifact_id="user-api")
        assert "SpringApplication.run(UserApiApplication.class, args)" in code

    def test_openapi_definition_annotation(self):
        code = _generate_main_app()
        assert "@OpenAPIDefinition" in code
        assert "@Info(" in code
        assert "@Server(" in code

    def test_openapi_imports(self):
        code = _generate_main_app()
        assert "import io.swagger.v3.oas.annotations.OpenAPIDefinition;" in code
        assert "import io.swagger.v3.oas.annotations.info.Info;" in code
        assert "import io.swagger.v3.oas.annotations.servers.Server;" in code

    def test_spring_boot_imports(self):
        code = _generate_main_app()
        assert "import org.springframework.boot.SpringApplication;" in code
        assert "import org.springframework.boot.autoconfigure.SpringBootApplication;" in code


# ═══════════════════════════════════════════════════════════════════
#  Conditional Annotations — @EnableScheduling
# ═══════════════════════════════════════════════════════════════════

class TestEnableScheduling:
    def test_enabled_when_scheduler_flow_exists(self):
        parsed = {
            "flows": [{"source": {"type": "scheduler"}, "processors": []}],
            "sub_flows": [], "batch_jobs": [],
        }
        code = _generate_main_app(parsed_data=parsed)
        assert "@EnableScheduling" in code
        assert "import org.springframework.scheduling.annotation.EnableScheduling;" in code

    def test_not_present_when_no_scheduler(self):
        parsed = {
            "flows": [{"source": {"type": "http-listener"}, "processors": []}],
            "sub_flows": [], "batch_jobs": [],
        }
        code = _generate_main_app(parsed_data=parsed)
        assert "@EnableScheduling" not in code


# ═══════════════════════════════════════════════════════════════════
#  Conditional Annotations — @EnableJms
# ═══════════════════════════════════════════════════════════════════

class TestEnableJms:
    def test_enabled_when_jms_connector(self):
        ci = {"connectors": {"jms"}, "dependencies": []}
        code = _generate_main_app(connector_info=ci)
        assert "@EnableJms" in code
        assert "import org.springframework.jms.annotation.EnableJms;" in code

    def test_not_present_when_no_jms(self):
        ci = {"connectors": {"http"}, "dependencies": []}
        code = _generate_main_app(connector_info=ci)
        assert "@EnableJms" not in code


# ═══════════════════════════════════════════════════════════════════
#  Conditional Annotations — @EnableCaching
# ═══════════════════════════════════════════════════════════════════

class TestEnableCaching:
    def test_enabled_when_redis_connector(self):
        ci = {"connectors": {"redis"}, "dependencies": []}
        code = _generate_main_app(connector_info=ci)
        assert "@EnableCaching" in code
        assert "import org.springframework.cache.annotation.EnableCaching;" in code

    def test_enabled_when_objectstore_connector(self):
        ci = {"connectors": {"objectstore"}, "dependencies": []}
        code = _generate_main_app(connector_info=ci)
        assert "@EnableCaching" in code

    def test_not_present_when_no_cache(self):
        ci = {"connectors": {"http"}, "dependencies": []}
        code = _generate_main_app(connector_info=ci)
        assert "@EnableCaching" not in code


# ═══════════════════════════════════════════════════════════════════
#  Conditional Annotations — Batch
# ═══════════════════════════════════════════════════════════════════

class TestBatchAnnotation:
    def test_batch_import_when_batch_connector(self):
        ci = {"connectors": {"batch"}, "dependencies": []}
        code = _generate_main_app(connector_info=ci)
        assert "EnableBatchProcessing" in code

    def test_batch_import_when_batch_jobs_exist(self):
        parsed = {
            "flows": [], "sub_flows": [],
            "batch_jobs": [{"name": "import-job"}],
        }
        code = _generate_main_app(parsed_data=parsed)
        assert "EnableBatchProcessing" in code


# ═══════════════════════════════════════════════════════════════════
#  Multiple Annotations Combined
# ═══════════════════════════════════════════════════════════════════

class TestCombinedAnnotations:
    def test_scheduler_plus_jms_plus_caching(self):
        parsed = {
            "flows": [{"source": {"type": "scheduler"}, "processors": []}],
            "sub_flows": [], "batch_jobs": [],
        }
        ci = {"connectors": {"jms", "redis"}, "dependencies": []}
        code = _generate_main_app(parsed_data=parsed, connector_info=ci)
        assert "@SpringBootApplication" in code
        assert "@EnableScheduling" in code
        assert "@EnableJms" in code
        assert "@EnableCaching" in code
