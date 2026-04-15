"""
Tests for generated Spring Boot Exception classes — validates
@ResponseStatus annotations, proper HTTP status codes, constructors,
and correct package/import structure.
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


@pytest.fixture
def gen():
    return SpringBootGenerator("test-app", "com.example", "17")


# ═══════════════════════════════════════════════════════════════════
#  ResourceNotFoundException
# ═══════════════════════════════════════════════════════════════════

class TestResourceNotFoundException:
    def test_response_status_404(self, gen):
        code = gen._gen_exception_class("ResourceNotFoundException")
        assert "@ResponseStatus(HttpStatus.NOT_FOUND)" in code

    def test_extends_runtime_exception(self, gen):
        code = gen._gen_exception_class("ResourceNotFoundException")
        assert "extends RuntimeException" in code

    def test_class_name(self, gen):
        code = gen._gen_exception_class("ResourceNotFoundException")
        assert "public class ResourceNotFoundException" in code

    def test_message_constructor(self, gen):
        code = gen._gen_exception_class("ResourceNotFoundException")
        assert "public ResourceNotFoundException(String message)" in code
        assert "super(message)" in code

    def test_cause_constructor(self, gen):
        code = gen._gen_exception_class("ResourceNotFoundException")
        assert "public ResourceNotFoundException(String message, Throwable cause)" in code
        assert "super(message, cause)" in code

    def test_package_declaration(self, gen):
        code = gen._gen_exception_class("ResourceNotFoundException")
        assert "package com.example.exception;" in code

    def test_imports(self, gen):
        code = gen._gen_exception_class("ResourceNotFoundException")
        assert "import org.springframework.http.HttpStatus;" in code
        assert "import org.springframework.web.bind.annotation.ResponseStatus;" in code


# ═══════════════════════════════════════════════════════════════════
#  BadRequestException
# ═══════════════════════════════════════════════════════════════════

class TestBadRequestException:
    def test_response_status_400(self, gen):
        code = gen._gen_exception_class("BadRequestException")
        assert "@ResponseStatus(HttpStatus.BAD_REQUEST)" in code

    def test_class_name(self, gen):
        code = gen._gen_exception_class("BadRequestException")
        assert "public class BadRequestException" in code


# ═══════════════════════════════════════════════════════════════════
#  UnauthorizedException
# ═══════════════════════════════════════════════════════════════════

class TestUnauthorizedException:
    def test_response_status_401(self, gen):
        code = gen._gen_exception_class("UnauthorizedException")
        assert "@ResponseStatus(HttpStatus.UNAUTHORIZED)" in code


# ═══════════════════════════════════════════════════════════════════
#  ServiceUnavailableException
# ═══════════════════════════════════════════════════════════════════

class TestServiceUnavailableException:
    def test_response_status_503(self, gen):
        code = gen._gen_exception_class("ServiceUnavailableException")
        assert "@ResponseStatus(HttpStatus.SERVICE_UNAVAILABLE)" in code


# ═══════════════════════════════════════════════════════════════════
#  TooManyRequestsException
# ═══════════════════════════════════════════════════════════════════

class TestTooManyRequestsException:
    def test_response_status_429(self, gen):
        code = gen._gen_exception_class("TooManyRequestsException")
        assert "@ResponseStatus(HttpStatus.TOO_MANY_REQUESTS)" in code


# ═══════════════════════════════════════════════════════════════════
#  Unknown Exception → Defaults to 500
# ═══════════════════════════════════════════════════════════════════

class TestUnknownException:
    def test_unknown_defaults_to_500(self, gen):
        code = gen._gen_exception_class("CustomAppException")
        assert "@ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)" in code

    def test_unknown_class_name(self, gen):
        code = gen._gen_exception_class("CustomAppException")
        assert "public class CustomAppException" in code


# ═══════════════════════════════════════════════════════════════════
#  Exception Files in Full Generation
# ═══════════════════════════════════════════════════════════════════

class TestExceptionFilesInFullGeneration:
    def test_all_five_exception_classes_generated(self):
        from backend.migrator.connector_mapper import ConnectorMapper
        gen = SpringBootGenerator("test-app", "com.example")
        mapper = ConnectorMapper()
        parsed = {
            "flows": [], "sub_flows": [], "connectors": set(),
            "batch_jobs": [], "global_configs": [], "secure_properties": [],
        }
        ci = mapper.map_connectors(parsed)
        files = gen.generate({}, ci, parsed)
        expected = [
            "ResourceNotFoundException.java",
            "BadRequestException.java",
            "UnauthorizedException.java",
            "ServiceUnavailableException.java",
            "TooManyRequestsException.java",
        ]
        for exc in expected:
            assert any(exc in k for k in files), f"Missing exception class: {exc}"

    def test_exception_files_under_exception_package(self):
        from backend.migrator.connector_mapper import ConnectorMapper
        gen = SpringBootGenerator("test-app", "com.example")
        mapper = ConnectorMapper()
        parsed = {
            "flows": [], "sub_flows": [], "connectors": set(),
            "batch_jobs": [], "global_configs": [], "secure_properties": [],
        }
        ci = mapper.map_connectors(parsed)
        files = gen.generate({}, ci, parsed)
        exc_files = {k: v for k, v in files.items() if "Exception.java" in k}
        for path in exc_files:
            assert "/exception/" in path
