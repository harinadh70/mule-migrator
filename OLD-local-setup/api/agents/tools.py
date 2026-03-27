"""
AgentTools — a lightweight tool registry that agents can invoke.

Each tool is a named, self-describing callable with typed parameters.
The registry ships with four built-in tools and supports runtime
registration of custom tools.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
#  Tool descriptor
# ---------------------------------------------------------------------------

@dataclass
class Tool:
    """Descriptor for a single tool an agent may invoke."""

    name: str
    description: str
    function: Callable[..., Any]
    parameters: Dict[str, str] = field(default_factory=dict)
    # e.g. {"xml_string": "str", "strict": "bool"}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# ---------------------------------------------------------------------------
#  Built-in tool implementations
# ---------------------------------------------------------------------------

def _parse_xml(xml_string: str) -> dict:
    """Parse a MuleSoft XML string and return a simplified dict representation.

    Uses the stdlib ``xml.etree.ElementTree`` so there are zero extra
    dependencies.
    """
    import xml.etree.ElementTree as ET

    def _elem_to_dict(elem: ET.Element) -> dict:
        result: Dict[str, Any] = {
            "tag": elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag,
            "namespace": elem.tag.split("}")[0].strip("{") if "}" in elem.tag else "",
            "attributes": dict(elem.attrib),
            "text": (elem.text or "").strip(),
            "children": [_elem_to_dict(child) for child in elem],
        }
        return result

    try:
        root = ET.fromstring(xml_string)
        return {"status": "ok", "root": _elem_to_dict(root)}
    except ET.ParseError as exc:
        return {"status": "error", "error": str(exc)}


def _validate_java(code: str) -> dict:
    """Quick structural validation of Java code.

    Returns a dict with ``valid`` (bool) and ``issues`` (list).
    """
    from api.agents.guardrails import AgentGuardrails

    is_valid, issues = AgentGuardrails.validate_java_syntax(code)
    _, ann_issues = AgentGuardrails.validate_spring_annotations(code)
    security = AgentGuardrails.detect_security_issues(code)

    return {
        "valid": is_valid and len(security) == 0,
        "syntax_issues": issues,
        "annotation_issues": ann_issues,
        "security_issues": security,
    }


def _search_rag(query: str, top_k: int = 5) -> List[dict]:
    """Search the RAG knowledge base.

    This is a *synchronous* wrapper.  In production the retriever is
    injected at startup; if it is not available we return an empty list.
    """
    try:
        from api.rag import HybridRetriever, RAGConfig

        config = RAGConfig()
        retriever = HybridRetriever(config)
        results = retriever.search(query, top_k=top_k)
        return results if isinstance(results, list) else []
    except Exception as exc:
        logger.warning("tool.search_rag.failed", error=str(exc))
        return []


def _get_spring_docs(topic: str) -> str:
    """Return curated Spring Boot documentation snippets for *topic*.

    Covers the most common migration targets; returns a concise reference
    rather than the full Spring docs.
    """
    _SNIPPETS: Dict[str, str] = {
        "rest_controller": (
            "@RestController combines @Controller + @ResponseBody.\n"
            "Use @GetMapping, @PostMapping, @PutMapping, @DeleteMapping.\n"
            "Inject services via constructor injection.\n"
            "Return ResponseEntity<T> for explicit status codes."
        ),
        "service": (
            "@Service marks a Spring-managed service bean.\n"
            "Use @Transactional for database operations.\n"
            "Prefer constructor injection over @Autowired."
        ),
        "jpa": (
            "Extend JpaRepository<Entity, ID> for CRUD.\n"
            "Use @Entity, @Table, @Id, @GeneratedValue.\n"
            "Spring Data derives queries from method names."
        ),
        "security": (
            "Spring Security 6+ uses SecurityFilterChain bean.\n"
            "Use @EnableWebSecurity, @EnableMethodSecurity.\n"
            "Configure via HttpSecurity.authorizeHttpRequests()."
        ),
        "testing": (
            "@WebMvcTest for controller-layer tests with MockMvc.\n"
            "@SpringBootTest for full integration tests.\n"
            "Use @MockBean to mock service dependencies.\n"
            "JUnit 5 + AssertJ is the standard stack."
        ),
        "properties": (
            "application.yml or application.properties for config.\n"
            "Use @Value(\"${key}\") or @ConfigurationProperties.\n"
            "Profile-specific: application-{profile}.yml."
        ),
        "error_handling": (
            "@ControllerAdvice + @ExceptionHandler for global error handling.\n"
            "Return ProblemDetail (RFC 7807) for API errors.\n"
            "Use ResponseStatusException for simple cases."
        ),
    }

    topic_lower = topic.lower().replace(" ", "_").replace("-", "_")
    if topic_lower in _SNIPPETS:
        return _SNIPPETS[topic_lower]

    # Fuzzy match
    for key, snippet in _SNIPPETS.items():
        if topic_lower in key or key in topic_lower:
            return snippet

    return f"No curated snippet for '{topic}'. Refer to https://docs.spring.io/spring-boot/docs/current/reference/html/"


# ---------------------------------------------------------------------------
#  Tool registry
# ---------------------------------------------------------------------------

class AgentTools:
    """Registry of tools agents can invoke by name."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}
        self._register_builtins()

    # ------------------------------------------------------------------
    #  Built-in registration
    # ------------------------------------------------------------------

    def _register_builtins(self) -> None:
        self.register_tool(Tool(
            name="parse_xml",
            description="Parse a MuleSoft XML string into a structured dict.",
            function=_parse_xml,
            parameters={"xml_string": "str"},
        ))
        self.register_tool(Tool(
            name="validate_java",
            description="Validate generated Java/Spring Boot code for syntax, annotations, and security.",
            function=_validate_java,
            parameters={"code": "str"},
        ))
        self.register_tool(Tool(
            name="search_rag",
            description="Search the RAG knowledge base for relevant MuleSoft/Spring Boot patterns.",
            function=_search_rag,
            parameters={"query": "str", "top_k": "int (default 5)"},
        ))
        self.register_tool(Tool(
            name="get_spring_docs",
            description="Get curated Spring Boot documentation snippets by topic.",
            function=_get_spring_docs,
            parameters={"topic": "str"},
        ))

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def register_tool(self, tool: Tool) -> None:
        """Register a new tool (or overwrite an existing one)."""
        self._tools[tool.name] = tool
        logger.debug("tools.registered", name=tool.name)

    def execute_tool(self, name: str, **kwargs: Any) -> Any:
        """Execute a registered tool by name.

        Raises:
            KeyError: If no tool with *name* exists.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}. Available: {list(self._tools.keys())}")

        logger.info("tools.execute", name=name, kwargs_keys=list(kwargs.keys()))
        try:
            return tool.function(**kwargs)
        except Exception as exc:
            logger.error("tools.execute.failed", name=name, error=str(exc))
            raise

    def list_tools(self) -> List[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def to_prompt_description(self) -> str:
        """Render all tools as a text block suitable for an LLM system prompt."""
        lines = ["Available tools:"]
        for tool in self._tools.values():
            params = ", ".join(f"{k}: {v}" for k, v in tool.parameters.items())
            lines.append(f"  - {tool.name}({params}): {tool.description}")
        return "\n".join(lines)
