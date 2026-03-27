"""
CoderAgent — generates Spring Boot code for unknown MuleSoft elements.

Wraps the existing conversion functions from ``backend.migrator.llm_agent``
and enhances them with RAG context, retry loops with syntax validation,
and structured tracking of RAG-vs-pure-LLM provenance.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import structlog

from api.agents.base import BaseAgent
from api.agents.context import AgentContext
from api.agents.guardrails import AgentGuardrails
from api.agents.result import AgentResult

# Import existing conversion functions
from backend.migrator.llm_agent import (
    AgentContext as LegacyAgentContext,
    convert_unknown_element,
    convert_unknown_dataweave,
    suggest_connector_mapping,
    convert_unknown_source,
    _extract_code_block,
)

logger = structlog.get_logger(__name__)


class CoderAgent(BaseAgent):
    """Generates Spring Boot code for elements the static pipeline cannot handle.

    For each unknown element the coder:
      1. Queries RAG for relevant Spring Boot patterns.
      2. Builds a prompt enriched with RAG context.
      3. Calls the LLM and validates the generated Java.
      4. Retries (up to ``max_retries``) if syntax validation fails.
      5. Falls back to existing ``backend.migrator.llm_agent`` functions
         when RAG-enhanced generation is not possible.
    """

    name = "coder"
    role = "Spring Boot code generation specialist"
    system_prompt = """You are a senior Java/Spring Boot 3.2 engineer specializing in
MuleSoft-to-Spring Boot migration.

For each unknown MuleSoft element you receive, generate production-ready Java code:
- Use Java 17 features (records, sealed classes, pattern matching where appropriate)
- Follow Spring Boot best practices (constructor injection, @Transactional, etc.)
- Include necessary import statements
- Add // REVIEW comments on uncertain parts
- Wrap code in ```java fences

If RAG context is provided, prefer patterns from the knowledge base over
inventing new approaches."""

    # ------------------------------------------------------------------
    #  Core execution
    # ------------------------------------------------------------------

    async def execute(self, context: AgentContext) -> AgentResult:
        """Process all unknown elements, generating code for each."""
        unknown_elements: List[dict] = context.get_artifact("unknown_elements") or []
        unknown_dataweave: List[dict] = context.get_artifact("unknown_dataweave") or []
        unknown_connectors: List[dict] = context.get_artifact("unknown_connectors") or []
        unknown_sources: List[dict] = context.get_artifact("unknown_sources") or []

        total_items = (
            len(unknown_elements) + len(unknown_dataweave)
            + len(unknown_connectors) + len(unknown_sources)
        )
        if total_items == 0:
            return AgentResult.success(
                output={"generated": {}, "message": "No unknown elements to process"},
            )

        generated: Dict[str, Any] = {}
        errors: List[str] = []
        total_tokens = 0
        rag_queries: List[str] = []
        rag_results_used = 0
        rag_sourced_count = 0
        llm_sourced_count = 0

        # --- Process unknown XML elements ----------------------------
        for item in unknown_elements:
            tag = item.get("tag", "unknown")
            xml = item.get("xml", "")
            flow_ctx = item.get("flow_context", "")

            code, tokens, rq, rr, from_rag = await self._generate_element_code(
                context, tag, xml, flow_ctx,
            )
            total_tokens += tokens
            rag_queries.extend(rq)
            rag_results_used += rr
            if from_rag:
                rag_sourced_count += 1
            else:
                llm_sourced_count += 1

            if code:
                generated[f"element:{tag}"] = code
            else:
                errors.append(f"Failed to generate code for element: {tag}")

        # --- Process unknown DataWeave expressions -------------------
        for item in unknown_dataweave:
            expr = item.get("expression", "")
            hint = item.get("context_hint", "")

            code, tokens, rq, rr, from_rag = await self._generate_dataweave_code(
                context, expr, hint,
            )
            total_tokens += tokens
            rag_queries.extend(rq)
            rag_results_used += rr
            if from_rag:
                rag_sourced_count += 1
            else:
                llm_sourced_count += 1

            if code:
                generated[f"dataweave:{expr[:40]}"] = code
            else:
                errors.append(f"Failed to convert DataWeave: {expr[:60]}")

        # --- Process unknown connectors ------------------------------
        for item in unknown_connectors:
            name = item.get("name", "")
            xml = item.get("xml", "")

            mapping, tokens = await self._generate_connector_mapping(
                context, name, xml,
            )
            total_tokens += tokens
            if mapping:
                generated[f"connector:{name}"] = mapping
            else:
                errors.append(f"Failed to map connector: {name}")

        # --- Process unknown sources ---------------------------------
        for item in unknown_sources:
            tag = item.get("tag", "")
            xml = item.get("xml", "")

            config, tokens = await self._generate_source_config(
                context, tag, xml,
            )
            total_tokens += tokens
            if config:
                generated[f"source:{tag}"] = config
            else:
                errors.append(f"Failed to convert source: {tag}")

        # Store results
        context.set_artifact("coder_generated", generated)
        context.update(self.name, {
            "generated_count": len(generated),
            "error_count": len(errors),
            "rag_sourced": rag_sourced_count,
            "llm_sourced": llm_sourced_count,
        })

        status = "success" if not errors else ("partial" if generated else "error")
        output = {
            "generated": generated,
            "errors": errors,
            "rag_sourced_count": rag_sourced_count,
            "llm_sourced_count": llm_sourced_count,
        }

        if status == "error":
            return AgentResult.from_error(
                error=f"{len(errors)} elements failed",
                fallback_output=output,
            )

        return AgentResult(
            status=status,
            output=output,
            token_usage=total_tokens,
            rag_queries=rag_queries,
            rag_results_used=rag_results_used,
            error="; ".join(errors) if errors else None,
        )

    # ------------------------------------------------------------------
    #  Element code generation with RAG + validation loop
    # ------------------------------------------------------------------

    async def _generate_element_code(
        self,
        context: AgentContext,
        element_tag: str,
        element_xml: str,
        flow_context: str,
    ) -> tuple[Optional[str], int, List[str], int, bool]:
        """Generate Java code for a single unknown element.

        Returns:
            (code, tokens_used, rag_queries, rag_results_used, from_rag)
        """
        rag_queries: List[str] = []
        rag_results_used = 0
        from_rag = False
        tokens = 0

        # 1. RAG search
        rag_context = ""
        if self.retriever is not None:
            query = f"Spring Boot equivalent for MuleSoft {element_tag}"
            rag_queries.append(query)
            results = await self.query_rag(query, top_k=5)
            if results:
                rag_results_used = len(results)
                rag_context = self.format_rag_results(results)
                from_rag = True

        # 2. Build prompt
        prompt = self._build_element_prompt(element_tag, element_xml, flow_context, rag_context)

        # 3. Generate with retry + validation loop
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self.call_llm_with_retry(prompt)
                tokens += len(prompt) // 4 + len(response) // 4
                code = self.extract_code_block(response)

                # 4. Validate syntax
                is_valid, issues = AgentGuardrails.validate_java_syntax(code)
                if is_valid:
                    cleaned = AgentGuardrails.validate(code, context)
                    return cleaned, tokens, rag_queries, rag_results_used, from_rag

                # Invalid — retry with feedback
                logger.warning(
                    "coder.validation_failed",
                    element=element_tag,
                    attempt=attempt,
                    issues=issues,
                )
                prompt += (
                    f"\n\nThe previous attempt had syntax issues: {issues}\n"
                    "Please fix and regenerate."
                )
            except Exception as exc:
                logger.warning(
                    "coder.llm_failed",
                    element=element_tag,
                    attempt=attempt,
                    error=str(exc),
                )

        # 5. Fallback to legacy function
        legacy_ctx = self._build_legacy_context(context)
        code = convert_unknown_element(legacy_ctx, element_tag, element_xml, flow_context)
        if code:
            return code, tokens, rag_queries, rag_results_used, False
        return None, tokens, rag_queries, rag_results_used, False

    # ------------------------------------------------------------------
    #  DataWeave code generation
    # ------------------------------------------------------------------

    async def _generate_dataweave_code(
        self,
        context: AgentContext,
        dw_expression: str,
        context_hint: str,
    ) -> tuple[Optional[str], int, List[str], int, bool]:
        """Convert a DataWeave expression to Java."""
        rag_queries: List[str] = []
        rag_results_used = 0
        from_rag = False
        tokens = 0

        # RAG search
        rag_context = ""
        if self.retriever is not None:
            query = f"Java equivalent of DataWeave expression: {dw_expression[:100]}"
            rag_queries.append(query)
            results = await self.query_rag(query, top_k=3)
            if results:
                rag_results_used = len(results)
                rag_context = self.format_rag_results(results)
                from_rag = True

        prompt = (
            f"Convert this DataWeave 2.0 expression to Java 17 code:\n\n"
            f"```dataweave\n{dw_expression}\n```\n"
        )
        if context_hint:
            prompt += f"\nContext: {context_hint}\n"
        if rag_context:
            prompt = f"=== Reference patterns ===\n{rag_context}\n=== End ===\n\n{prompt}"

        try:
            response = await self.call_llm_with_retry(prompt)
            tokens = len(prompt) // 4 + len(response) // 4
            code = self.extract_code_block(response)
            return code, tokens, rag_queries, rag_results_used, from_rag
        except Exception:
            # Fallback
            legacy_ctx = self._build_legacy_context(context)
            code = convert_unknown_dataweave(legacy_ctx, dw_expression, context_hint)
            return code, tokens, rag_queries, rag_results_used, False

    # ------------------------------------------------------------------
    #  Connector mapping
    # ------------------------------------------------------------------

    async def _generate_connector_mapping(
        self,
        context: AgentContext,
        connector_name: str,
        connector_xml: str,
    ) -> tuple[Optional[dict], int]:
        """Suggest Maven deps and properties for an unknown connector."""
        tokens = 0
        try:
            prompt = (
                f"Suggest Spring Boot equivalents for MuleSoft connector: {connector_name}\n"
            )
            if connector_xml:
                prompt += f"Config XML:\n{connector_xml}\n"
            prompt += (
                "\nReturn JSON with: maven_dependencies, spring_properties, notes\n"
                "Wrap in ```json fence."
            )
            response = await self.call_llm_with_retry(prompt)
            tokens = len(prompt) // 4 + len(response) // 4
            result = self.parse_response(response)
            if "maven_dependencies" in result:
                return result, tokens
        except Exception:
            pass

        # Fallback
        legacy_ctx = self._build_legacy_context(context)
        result = suggest_connector_mapping(legacy_ctx, connector_name, connector_xml)
        return result, tokens

    # ------------------------------------------------------------------
    #  Source config
    # ------------------------------------------------------------------

    async def _generate_source_config(
        self,
        context: AgentContext,
        source_tag: str,
        source_xml: str,
    ) -> tuple[Optional[dict], int]:
        """Convert an unknown message source to Spring Boot config."""
        tokens = 0
        try:
            prompt = (
                f"Convert this MuleSoft message source to Spring Boot config:\n"
                f"Source: {source_tag}\nXML:\n{source_xml}\n"
                "\nReturn JSON with: type, config, spring_annotation, notes\n"
                "Wrap in ```json fence."
            )
            response = await self.call_llm_with_retry(prompt)
            tokens = len(prompt) // 4 + len(response) // 4
            result = self.parse_response(response)
            if "type" in result:
                return result, tokens
        except Exception:
            pass

        legacy_ctx = self._build_legacy_context(context)
        result = convert_unknown_source(legacy_ctx, source_tag, source_xml)
        return result, tokens

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _build_element_prompt(
        self,
        tag: str,
        xml: str,
        flow_context: str,
        rag_context: str,
    ) -> str:
        parts: List[str] = []
        if rag_context:
            parts.append("=== Relevant patterns from knowledge base ===")
            parts.append(rag_context)
            parts.append("=== End patterns ===\n")

        parts.append(f"Convert this MuleSoft XML element to Spring Boot Java code:\n")
        parts.append(f"Element: {tag}")
        parts.append(f"XML:\n{xml}\n")
        if flow_context:
            parts.append(f"Flow context: {flow_context}\n")
        parts.append("Return ONLY Java code in a ```java fence.")
        return "\n".join(parts)

    @staticmethod
    def _build_legacy_context(context: AgentContext) -> LegacyAgentContext:
        """Create a legacy AgentContext compatible with backend.migrator functions."""
        # The extended AgentContext *is* a LegacyAgentContext, so just return it.
        # But if for some reason the caller has a stripped-down context, build one.
        if isinstance(context, LegacyAgentContext):
            return context
        return LegacyAgentContext(
            enabled=context.enabled,
            llm_config=context.llm_config,
        )

    # ------------------------------------------------------------------
    #  Fallback
    # ------------------------------------------------------------------

    def get_fallback(self, context: AgentContext) -> dict:
        """Produce TODO stubs for every unknown element."""
        unknowns = context.get_artifact("unknown_elements") or []
        stubs: Dict[str, str] = {}
        for item in unknowns:
            tag = item.get("tag", "unknown")
            stubs[f"element:{tag}"] = (
                f"// TODO: Manually convert MuleSoft element <{tag}> to Spring Boot\n"
                f"// Original XML:\n// {item.get('xml', '')[:200]}\n"
            )
        return {"generated": stubs, "errors": [], "fallback": True}
