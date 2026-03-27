"""
Secure MuleSoft XML validator.

Validates uploaded XML content for structural correctness, MuleSoft
namespace presence, and enforces safety constraints (file size, XXE
prevention via defusedxml).
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Maximum allowed XML content size: 10 MB
MAX_XML_SIZE_BYTES = 10 * 1024 * 1024

# Common MuleSoft namespace URIs
MULESOFT_NAMESPACES = frozenset(
    {
        "http://www.mulesoft.org/schema/mule/core",
        "http://www.mulesoft.org/schema/mule/http",
        "http://www.mulesoft.org/schema/mule/ee/core",
        "http://www.mulesoft.org/schema/mule/db",
        "http://www.mulesoft.org/schema/mule/apikit",
        "http://www.mulesoft.org/schema/mule/file",
        "http://www.mulesoft.org/schema/mule/vm",
        "http://www.mulesoft.org/schema/mule/json",
        "http://www.mulesoft.org/schema/mule/xml",
        "http://www.mulesoft.org/schema/mule/jms",
        "http://www.mulesoft.org/schema/mule/sftp",
        "http://www.mulesoft.org/schema/mule/ftp",
        "http://www.mulesoft.org/schema/mule/oauth2-provider",
        "http://www.mulesoft.org/schema/mule/secure-properties",
    }
)


def validate_mulesoft_xml(content: str) -> dict[str, Any]:
    """
    Validate XML content intended as a MuleSoft configuration file.

    Performs the following checks:
      1. Content is not empty.
      2. Content does not exceed ``MAX_XML_SIZE_BYTES``.
      3. Content is well-formed XML (parsed with defusedxml to block XXE).
      4. Root tag and declared namespaces are extracted.
      5. At least one recognised MuleSoft namespace is present (warning if not).

    Parameters
    ----------
    content : str
        Raw XML string.

    Returns
    -------
    dict
        ``valid``       — ``True`` if parsing succeeded and basic checks passed.
        ``errors``      — List of error strings (empty when valid).
        ``warnings``    — List of warning strings.
        ``root_tag``    — Local name of the root element (empty on parse failure).
        ``namespaces``  — List of namespace URIs found in the document.
    """
    result: dict[str, Any] = {
        "valid": False,
        "errors": [],
        "warnings": [],
        "root_tag": "",
        "namespaces": [],
    }

    # ── 1. Empty check ───────────────────────────────────────────
    if not content or not content.strip():
        result["errors"].append("XML content is empty.")
        return result

    # ── 2. Size check ────────────────────────────────────────────
    content_bytes = len(content.encode("utf-8"))
    if content_bytes > MAX_XML_SIZE_BYTES:
        result["errors"].append(
            f"XML content exceeds maximum allowed size of "
            f"{MAX_XML_SIZE_BYTES // (1024 * 1024)} MB "
            f"(received {content_bytes:,} bytes)."
        )
        return result

    # ── 3. Parse with defusedxml (XXE-safe) ──────────────────────
    try:
        import defusedxml.ElementTree as DefusedET

        root = DefusedET.fromstring(content)
    except Exception as exc:
        result["errors"].append(f"XML parsing failed: {exc}")
        logger.warning("xml_validator.parse_error", error=str(exc))
        return result

    # ── 4. Extract root tag and namespaces ───────────────────────
    # ElementTree encodes the namespace in Clark notation: {uri}localname
    tag = root.tag
    if tag.startswith("{"):
        ns_end = tag.index("}")
        root_ns = tag[1:ns_end]
        local_name = tag[ns_end + 1 :]
    else:
        root_ns = ""
        local_name = tag

    result["root_tag"] = local_name

    # Collect all namespace URIs used in the document
    namespaces: set[str] = set()
    if root_ns:
        namespaces.add(root_ns)

    for elem in root.iter():
        elem_tag = elem.tag if isinstance(elem.tag, str) else ""
        if elem_tag.startswith("{"):
            ns_end = elem_tag.index("}")
            namespaces.add(elem_tag[1:ns_end])
        # Also check attributes for namespace-qualified names
        for attr_name in elem.attrib:
            if attr_name.startswith("{"):
                ns_end = attr_name.index("}")
                namespaces.add(attr_name[1:ns_end])

    result["namespaces"] = sorted(namespaces)

    # ── 5. MuleSoft namespace check ──────────────────────────────
    has_mulesoft_ns = bool(namespaces & MULESOFT_NAMESPACES)
    if not has_mulesoft_ns:
        result["warnings"].append(
            "No recognised MuleSoft namespace found. "
            "The file may not be a valid MuleSoft configuration."
        )

    result["valid"] = True
    logger.info(
        "xml_validator.success",
        root_tag=local_name,
        namespace_count=len(namespaces),
        has_mulesoft_ns=has_mulesoft_ns,
    )
    return result
