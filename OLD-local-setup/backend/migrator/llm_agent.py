"""
LLM Conversion Module — Handles real-time code generation for unknown MuleSoft elements.

When the static converters encounter an element they don't recognise, they delegate
to the functions in this module.  Each function builds a specialised prompt, calls
the configured LLM provider, and returns usable code or config.

Conversion strategy (triple fallback):
  1. LLM-generated code  →  2. TODO comment  →  3. warning in summary

Public functions:
  - convert_unknown_element()   — unknown XML processors → Java code
  - convert_unknown_dataweave() — unparseable DW expressions → Java code
  - suggest_connector_mapping() — unknown connectors → Maven deps + properties
  - convert_unknown_source()    — unknown message sources → config dict
"""
import logging
import re
from typing import Optional

from .llm_validator import chat_with_llm

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  AgentContext — shared state that flows through the migration pipeline
# ══════════════════════════════════════════════════════════════════════════════
class AgentContext:
    """Shared context threaded through every pipeline stage.

    Attributes:
        enabled: Whether LLM-assisted conversion is turned on.
        llm_config: Provider configuration dict with keys:
            provider, apiKey, model, baseUrl (optional).
        conversions: List of successful conversions for the summary.
        skipped: List of items skipped because LLM was disabled or failed.
    """

    def __init__(self, enabled: bool = False, llm_config: dict = None):
        self.enabled = enabled
        self.llm_config = llm_config or {}
        self.conversions = []   # [{element, prompt_summary, generated_code}]
        self.skipped = []       # [{element, reason}]

    def record_conversion(self, element: str, prompt_summary: str,
                          generated_code: str):
        """Record a successful conversion."""
        self.conversions.append({
            "element": element,
            "prompt_summary": prompt_summary,
            "generated_code": generated_code[:500],  # truncate for summary
        })

    def record_skipped(self, element: str, reason: str):
        """Record an item that was skipped (LLM disabled or call failed)."""
        self.skipped.append({
            "element": element,
            "reason": reason,
        })

    def to_summary(self) -> dict:
        """Return summary data for the API response."""
        return {
            "llmAssisted": self.enabled,
            "autoConversions": self.conversions,
            "autoConversionCount": len(self.conversions),
            "conversionSkipped": self.skipped,
            "conversionSkippedCount": len(self.skipped),
        }


# ══════════════════════════════════════════════════════════════════════════════
#  Internal LLM call helper
# ══════════════════════════════════════════════════════════════════════════════
def _call_llm(agent_ctx: AgentContext, system_prompt: str,
              user_prompt: str) -> Optional[str]:
    """Call the LLM via the agent context's config.

    Returns the raw text response, or None on failure.
    """
    if not agent_ctx.enabled:
        return None
    if not agent_ctx.llm_config.get("provider"):
        return None
    try:
        return chat_with_llm(agent_ctx.llm_config, system_prompt, user_prompt)
    except Exception as e:
        logger.warning("LLM call failed: %s", e)
        return None


def _extract_code_block(response: str) -> str:
    """Extract code from markdown fenced blocks in LLM response."""
    m = re.search(r'```(?:java)?\s*\n(.*?)```', response, re.DOTALL)
    if m:
        return m.group(1).strip()
    return response.strip()


# ══════════════════════════════════════════════════════════════════════════════
#  Convert Unknown XML Element → Java Code
# ══════════════════════════════════════════════════════════════════════════════
ELEMENT_SYSTEM_PROMPT = """You are a senior Java/Spring Boot engineer.
You are given an unknown MuleSoft XML element that needs to be converted to
equivalent Spring Boot 3.2 / Java 17 code.

Rules:
- Return ONLY the Java code (method body or statements), no explanations.
- Use Spring Boot best practices (annotations, dependency injection).
- Include necessary import statements as comments at the top.
- If you cannot determine the exact equivalent, provide the closest approximation
  with a // REVIEW comment on uncertain parts.
- Wrap the code in a ```java code fence."""


def convert_unknown_element(agent_ctx: AgentContext, element_tag: str,
                            element_xml: str, flow_context: str = "") -> Optional[str]:
    """Convert an unknown MuleSoft XML processor element to Java code.

    Args:
        agent_ctx: The shared pipeline context.
        element_tag: The XML tag name (e.g., 'salesforce:query').
        element_xml: The raw XML string of the element.
        flow_context: Optional description of the surrounding flow.

    Returns:
        Java code string, or None if unavailable.
    """
    if not agent_ctx.enabled:
        agent_ctx.record_skipped(element_tag, "LLM-assisted conversion disabled")
        return None

    user_prompt = (
        f"Convert this MuleSoft XML element to Spring Boot Java code:\n\n"
        f"Element: {element_tag}\n"
        f"XML:\n{element_xml}\n"
    )
    if flow_context:
        user_prompt += f"\nFlow context: {flow_context}\n"

    response = _call_llm(agent_ctx, ELEMENT_SYSTEM_PROMPT, user_prompt)
    if response:
        code = _extract_code_block(response)
        agent_ctx.record_conversion(element_tag, f"Unknown processor: {element_tag}",
                                    code)
        return code

    agent_ctx.record_skipped(element_tag, "LLM call failed")
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  Convert Unknown DataWeave Expression → Java Code
# ══════════════════════════════════════════════════════════════════════════════
DATAWEAVE_SYSTEM_PROMPT = """You are a senior Java engineer who specializes in
converting MuleSoft DataWeave 2.0 expressions to equivalent Java code.

Rules:
- Return ONLY the Java expression or statement(s), no explanations.
- Use Java streams, lambdas, and standard library where appropriate.
- For complex transformations, use Jackson ObjectMapper or similar.
- Include necessary import statements as comments at the top.
- Wrap the code in a ```java code fence."""


def convert_unknown_dataweave(agent_ctx: AgentContext, dw_expression: str,
                              context_hint: str = "") -> Optional[str]:
    """Convert an unparseable DataWeave expression to Java code.

    Args:
        agent_ctx: The shared pipeline context.
        dw_expression: The DataWeave expression that could not be parsed.
        context_hint: Optional hint about what the expression does.

    Returns:
        Java code string, or None if unavailable.
    """
    if not agent_ctx.enabled:
        agent_ctx.record_skipped(f"DataWeave: {dw_expression[:80]}",
                                 "LLM-assisted conversion disabled")
        return None

    user_prompt = (
        f"Convert this DataWeave 2.0 expression to Java:\n\n"
        f"```dataweave\n{dw_expression}\n```\n"
    )
    if context_hint:
        user_prompt += f"\nContext: {context_hint}\n"

    response = _call_llm(agent_ctx, DATAWEAVE_SYSTEM_PROMPT, user_prompt)
    if response:
        code = _extract_code_block(response)
        agent_ctx.record_conversion(
            f"DataWeave: {dw_expression[:60]}",
            "Unparseable DataWeave expression",
            code,
        )
        return code

    agent_ctx.record_skipped(f"DataWeave: {dw_expression[:80]}",
                             "LLM call failed")
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  Suggest Connector Mapping → Maven Deps + Properties
# ══════════════════════════════════════════════════════════════════════════════
CONNECTOR_SYSTEM_PROMPT = """You are a senior Java/Spring Boot engineer.
Given an unknown MuleSoft connector, suggest the equivalent Spring Boot
Maven dependencies and application properties.

Return ONLY a JSON object with this structure:
{
  "maven_dependencies": [
    {"groupId": "...", "artifactId": "...", "version": "..."}
  ],
  "spring_properties": {
    "property.key": "property-value"
  },
  "notes": "Brief note about the mapping"
}

No explanations outside the JSON. Wrap in ```json fence."""


def suggest_connector_mapping(agent_ctx: AgentContext, connector_name: str,
                              connector_xml: str = "") -> Optional[dict]:
    """Suggest Maven dependencies and Spring properties for an unknown connector.

    Args:
        agent_ctx: The shared pipeline context.
        connector_name: The connector namespace/name (e.g., 'twilio').
        connector_xml: Optional raw XML of the connector config.

    Returns:
        Dict with 'maven_dependencies' and 'spring_properties', or None.
    """
    import json

    if not agent_ctx.enabled:
        agent_ctx.record_skipped(f"Connector: {connector_name}",
                                 "LLM-assisted conversion disabled")
        return None

    user_prompt = (
        f"Suggest Spring Boot equivalents for this MuleSoft connector:\n\n"
        f"Connector: {connector_name}\n"
    )
    if connector_xml:
        user_prompt += f"Config XML:\n{connector_xml}\n"

    response = _call_llm(agent_ctx, CONNECTOR_SYSTEM_PROMPT, user_prompt)
    if response:
        code = _extract_code_block(response)
        try:
            result = json.loads(code)
            agent_ctx.record_conversion(
                f"Connector: {connector_name}",
                "Unknown connector mapping",
                json.dumps(result, indent=2),
            )
            return result
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON for connector %s",
                           connector_name)

    agent_ctx.record_skipped(f"Connector: {connector_name}", "LLM call failed")
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  Convert Unknown Source → Config Dict
# ══════════════════════════════════════════════════════════════════════════════
SOURCE_SYSTEM_PROMPT = """You are a senior Java/Spring Boot engineer.
Given an unknown MuleSoft message source (listener/inbound endpoint),
determine the equivalent Spring Boot configuration.

Return ONLY a JSON object with this structure:
{
  "type": "http|jms|scheduler|file|custom",
  "config": {
    "key": "value"
  },
  "spring_annotation": "@GetMapping or similar",
  "notes": "Brief explanation"
}

No extra text. Wrap in ```json fence."""


def convert_unknown_source(agent_ctx: AgentContext, source_tag: str,
                           source_xml: str) -> Optional[dict]:
    """Convert an unknown MuleSoft message source to a config dict.

    Args:
        agent_ctx: The shared pipeline context.
        source_tag: The XML tag name of the source.
        source_xml: The raw XML of the source element.

    Returns:
        Dict with source config, or None if unavailable.
    """
    import json

    if not agent_ctx.enabled:
        agent_ctx.record_skipped(f"Source: {source_tag}",
                                 "LLM-assisted conversion disabled")
        return None

    user_prompt = (
        f"Convert this MuleSoft message source to Spring Boot config:\n\n"
        f"Source: {source_tag}\n"
        f"XML:\n{source_xml}\n"
    )

    response = _call_llm(agent_ctx, SOURCE_SYSTEM_PROMPT, user_prompt)
    if response:
        code = _extract_code_block(response)
        try:
            result = json.loads(code)
            agent_ctx.record_conversion(
                f"Source: {source_tag}",
                "Unknown message source",
                json.dumps(result, indent=2),
            )
            return result
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON for source %s", source_tag)

    agent_ctx.record_skipped(f"Source: {source_tag}", "LLM call failed")
    return None
