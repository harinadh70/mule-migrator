"""
Tests for the MuleSoft XML validator.

Covers well-formed MuleSoft XML, invalid XML, XXE attack prevention,
oversized input rejection, and non-MuleSoft XML detection.
"""

from __future__ import annotations

import pytest

from api.services.xml_validator import MAX_XML_SIZE_BYTES, validate_mulesoft_xml


# ── Fixtures ──────────────────────────────────────────────────────

VALID_MULESOFT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="
        http://www.mulesoft.org/schema/mule/core
        http://www.mulesoft.org/schema/mule/core/current/mule.xsd
        http://www.mulesoft.org/schema/mule/http
        http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd">

    <http:listener-config name="HTTP_Listener_config" host="0.0.0.0" port="8081" />

    <flow name="hello-world-flow">
        <http:listener config-ref="HTTP_Listener_config" path="/hello" />
        <set-payload value="Hello, World!" />
    </flow>
</mule>
"""

NON_MULESOFT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>my-app</artifactId>
</project>
"""

MALFORMED_XML = "<root><unclosed>"

XXE_PAYLOAD = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<mule xmlns="http://www.mulesoft.org/schema/mule/core">
    <flow name="&xxe;" />
</mule>
"""


# ── Tests ─────────────────────────────────────────────────────────


def test_valid_mulesoft_xml():
    """A well-formed MuleSoft XML file should validate successfully."""
    result = validate_mulesoft_xml(VALID_MULESOFT_XML)

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["root_tag"] == "mule"
    assert len(result["namespaces"]) > 0
    assert any(
        "mulesoft.org" in ns for ns in result["namespaces"]
    ), "Expected at least one MuleSoft namespace"


def test_invalid_xml_rejected():
    """Malformed XML should be flagged as invalid with a parse error."""
    result = validate_mulesoft_xml(MALFORMED_XML)

    assert result["valid"] is False
    assert len(result["errors"]) > 0
    assert any("pars" in err.lower() for err in result["errors"])


def test_xxe_attack_blocked():
    """
    An XML document containing an XXE entity definition must be rejected
    by the defusedxml parser.
    """
    result = validate_mulesoft_xml(XXE_PAYLOAD)

    # defusedxml should raise an error for DOCTYPE with entity definitions
    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_oversized_xml_rejected():
    """XML content exceeding the maximum size limit should be rejected."""
    oversized_content = "<root>" + ("x" * (MAX_XML_SIZE_BYTES + 1)) + "</root>"
    result = validate_mulesoft_xml(oversized_content)

    assert result["valid"] is False
    assert len(result["errors"]) > 0
    assert any("size" in err.lower() or "exceeds" in err.lower() for err in result["errors"])


def test_non_mulesoft_xml_warning():
    """
    Valid XML without MuleSoft namespaces should parse successfully
    but include a warning about missing MuleSoft namespaces.
    """
    result = validate_mulesoft_xml(NON_MULESOFT_XML)

    assert result["valid"] is True
    assert result["errors"] == []
    assert len(result["warnings"]) > 0
    assert any("mulesoft" in w.lower() for w in result["warnings"])


def test_empty_xml_rejected():
    """Empty or whitespace-only input should be rejected."""
    result = validate_mulesoft_xml("")
    assert result["valid"] is False
    assert len(result["errors"]) > 0

    result_ws = validate_mulesoft_xml("   \n\t  ")
    assert result_ws["valid"] is False
    assert len(result_ws["errors"]) > 0
