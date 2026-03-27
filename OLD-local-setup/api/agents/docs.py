"""
DocsAgent — generates project documentation and migration reports.

Produces:
  - README.md with setup instructions and architecture overview
  - MIGRATION_REPORT.md with detailed conversion audit
  - Enhanced Swagger/OpenAPI spec with request/response examples
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

from api.agents.base import BaseAgent
from api.agents.context import AgentContext
from api.agents.result import AgentResult

logger = structlog.get_logger(__name__)


class DocsAgent(BaseAgent):
    """Generates documentation artifacts for migrated Spring Boot projects."""

    name = "docs"
    role = "technical documentation specialist"
    system_prompt = """You are a senior technical writer specializing in Spring Boot project documentation.

Generate clear, structured documentation for a project that was migrated from MuleSoft to Spring Boot.

For README.md, include:
- Project overview and what was migrated
- Prerequisites (Java 17, Maven/Gradle, etc.)
- How to build and run
- API endpoints summary
- Configuration properties
- Known limitations from migration

For MIGRATION_REPORT.md, include:
- Executive summary
- Migration scope (files converted, connectors mapped)
- Items requiring manual review (with file and line references)
- Risk assessment
- Recommendations

Return the documentation as a JSON object:
{
  "readme": "<full README.md content>",
  "migration_report": "<full MIGRATION_REPORT.md content>"
}"""

    # ------------------------------------------------------------------
    #  Core execution
    # ------------------------------------------------------------------

    async def execute(self, context: AgentContext) -> AgentResult:
        """Generate all documentation artifacts."""
        generated_files = context.get_artifact("generated_files") or {}
        migration_plan = context.get_artifact("migration_plan") or {}
        review_feedback = context.get_artifact("review_feedback") or []
        coder_result = context.get_agent_result("coder") or {}
        test_files = context.get_artifact("test_files") or {}

        total_tokens = 0
        rag_queries: List[str] = []
        rag_results_used = 0

        # 1. RAG: retrieve documentation templates
        rag_context = ""
        if self.retriever is not None:
            query = "Spring Boot project documentation template migration report"
            rag_queries.append(query)
            results = await self.query_rag(query, top_k=3)
            if results:
                rag_results_used = len(results)
                rag_context = self.format_rag_results(results)

        # 2. Collect metadata for docs
        metadata = self._collect_metadata(
            context, generated_files, migration_plan, review_feedback,
            coder_result, test_files,
        )

        # 3. Try LLM-enhanced documentation
        docs: Dict[str, str] = {}
        try:
            prompt = self._build_docs_prompt(metadata, rag_context)
            response = await self.call_llm_with_retry(prompt)
            total_tokens = len(prompt) // 4 + len(response) // 4

            parsed = self.parse_response(response)
            if "readme" in parsed:
                docs["README.md"] = parsed["readme"]
            if "migration_report" in parsed:
                docs["MIGRATION_REPORT.md"] = parsed["migration_report"]
        except Exception as exc:
            logger.warning("docs.llm_failed", error=str(exc))

        # 4. Fallback: generate docs from templates
        if "README.md" not in docs:
            docs["README.md"] = self._generate_readme(metadata)
        if "MIGRATION_REPORT.md" not in docs:
            docs["MIGRATION_REPORT.md"] = self._generate_migration_report(metadata)

        # 5. Generate OpenAPI enhancements
        openapi_enhancements = self._enhance_openapi(generated_files)
        if openapi_enhancements:
            docs["openapi_enhancements.json"] = json.dumps(
                openapi_enhancements, indent=2,
            )

        # Store docs
        all_files = dict(generated_files)
        all_files.update(docs)
        context.set_artifact("generated_files", all_files)
        context.set_artifact("documentation", docs)

        context.update(self.name, {
            "docs_generated": list(docs.keys()),
            "doc_count": len(docs),
        })

        return AgentResult.success(
            output={
                "docs": {k: v[:200] + "..." for k, v in docs.items()},
                "doc_count": len(docs),
            },
            token_usage=total_tokens,
            rag_queries=rag_queries,
            rag_results_used=rag_results_used,
        )

    # ------------------------------------------------------------------
    #  Metadata collection
    # ------------------------------------------------------------------

    def _collect_metadata(
        self,
        context: AgentContext,
        generated_files: Dict[str, str],
        migration_plan: dict,
        review_feedback: list,
        coder_result: dict,
        test_files: Dict[str, str],
    ) -> dict:
        java_files = [f for f in generated_files if f.endswith(".java")]
        config_files = [
            f for f in generated_files
            if f.endswith((".properties", ".yml", ".yaml"))
        ]

        # Extract endpoints from controller files
        endpoints: List[dict] = []
        for fp, content in generated_files.items():
            if "controller" in fp.lower() or "@RestController" in content:
                import re
                for m in re.finditer(
                    r'@(Get|Post|Put|Delete|Patch)Mapping\(\s*["\']?([^"\')\s]+)',
                    content,
                ):
                    endpoints.append({
                        "method": m.group(1).upper(),
                        "path": m.group(2),
                        "file": fp,
                    })

        return {
            "project_name": "migrated-springboot-app",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": context.id,
            "java_files": java_files,
            "config_files": config_files,
            "test_files": list(test_files.keys()),
            "total_files": len(generated_files),
            "endpoints": endpoints,
            "migration_plan": migration_plan,
            "review_feedback": review_feedback,
            "coder_result": coder_result,
            "token_usage": context.token_usage,
            "total_cost_usd": context.total_cost_usd,
            "complexity": migration_plan.get("complexity", "unknown"),
            "connectors": migration_plan.get("connectors_detected", []),
            "risk_areas": migration_plan.get("risk_areas", []),
        }

    # ------------------------------------------------------------------
    #  Prompt
    # ------------------------------------------------------------------

    def _build_docs_prompt(self, metadata: dict, rag_context: str) -> str:
        parts: List[str] = []

        if rag_context:
            parts.append("=== Documentation templates ===")
            parts.append(rag_context)
            parts.append("=== End templates ===\n")

        parts.append("Generate documentation for this migrated Spring Boot project:\n")
        parts.append(f"Migration complexity: {metadata['complexity']}")
        parts.append(f"Java files: {len(metadata['java_files'])}")
        parts.append(f"Test files: {len(metadata['test_files'])}")
        parts.append(f"Connectors migrated: {', '.join(metadata['connectors'])}")
        parts.append(f"Risk areas: {len(metadata['risk_areas'])}")

        if metadata["endpoints"]:
            parts.append("\nAPI Endpoints:")
            for ep in metadata["endpoints"][:20]:
                parts.append(f"  {ep['method']} {ep['path']} ({ep['file']})")

        if metadata["risk_areas"]:
            parts.append("\nRisk areas:")
            for risk in metadata["risk_areas"][:10]:
                parts.append(f"  - {risk}")

        # Review summary
        reviews = metadata.get("review_feedback", [])
        if reviews:
            scores = [r.get("score", 0) for r in reviews if isinstance(r, dict)]
            if scores:
                parts.append(f"\nCode review average score: {sum(scores)/len(scores):.1f}/10")

        parts.append("\nReturn JSON with 'readme' and 'migration_report' keys.")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    #  Template-based fallback generators
    # ------------------------------------------------------------------

    def _generate_readme(self, metadata: dict) -> str:
        endpoints_section = ""
        if metadata["endpoints"]:
            endpoint_lines = "\n".join(
                f"| `{ep['method']}` | `{ep['path']}` | {ep['file']} |"
                for ep in metadata["endpoints"][:20]
            )
            endpoints_section = f"""
## API Endpoints

| Method | Path | Source |
|--------|------|--------|
{endpoint_lines}
"""

        connectors = ", ".join(metadata["connectors"]) if metadata["connectors"] else "None detected"

        return f"""# {metadata['project_name']}

> Auto-migrated from MuleSoft to Spring Boot 3.2 on {metadata['generated_at'][:10]}

## Overview

This Spring Boot application was automatically migrated from a MuleSoft 4 application.
Migration complexity: **{metadata['complexity']}**.

### Files Generated
- Java source files: {len(metadata['java_files'])}
- Configuration files: {len(metadata['config_files'])}
- Test files: {len(metadata['test_files'])}
- Total files: {metadata['total_files']}

### Connectors Migrated
{connectors}

## Prerequisites

- Java 17+
- Maven 3.8+ or Gradle 8+
- Spring Boot 3.2

## Build & Run

```bash
# Build
./mvnw clean package

# Run
./mvnw spring-boot:run

# Run tests
./mvnw test
```
{endpoints_section}
## Configuration

Application properties are in `src/main/resources/application.properties`.
Review and update database URLs, API keys, and service endpoints.

## Known Limitations

{self._format_risk_areas(metadata['risk_areas'])}

## Migration Details

See [MIGRATION_REPORT.md](MIGRATION_REPORT.md) for a detailed migration audit.

---
*Generated by MuleSoft-to-SpringBoot Migrator (run: {metadata['run_id'][:8]})*
"""

    def _generate_migration_report(self, metadata: dict) -> str:
        coder = metadata.get("coder_result", {})
        reviews = metadata.get("review_feedback", [])

        # Review summary
        review_section = ""
        if reviews:
            scores = [r.get("score", 0) for r in reviews if isinstance(r, dict)]
            avg_score = sum(scores) / len(scores) if scores else 0
            review_section = f"""
## Code Review Summary

- Files reviewed: {len(reviews)}
- Average quality score: **{avg_score:.1f}/10**

### Per-file Scores

| File | Score | Issues |
|------|-------|--------|
"""
            for r in reviews:
                if isinstance(r, dict):
                    fb_count = len(r.get("feedback", []))
                    review_section += f"| {r.get('filepath', 'N/A')} | {r.get('score', 'N/A')}/10 | {fb_count} |\n"

        # Manual review items
        manual_items = []
        for r in reviews:
            if isinstance(r, dict):
                for fb in r.get("feedback", []):
                    if isinstance(fb, dict) and fb.get("severity") == "critical":
                        manual_items.append(
                            f"- **{r.get('filepath', '?')}** "
                            f"(line {fb.get('line', '?')}): {fb.get('message', '')}"
                        )

        manual_section = ""
        if manual_items:
            manual_section = "## Items Requiring Manual Review\n\n" + "\n".join(manual_items[:30])

        return f"""# Migration Report

**Generated:** {metadata['generated_at'][:10]}
**Run ID:** {metadata['run_id']}

## Executive Summary

MuleSoft application migrated to Spring Boot 3.2 with **{metadata['complexity']}** complexity.
- {len(metadata['java_files'])} Java files generated
- {len(metadata['test_files'])} test files generated
- {len(metadata['connectors'])} connectors mapped

## Migration Scope

### Connectors Migrated
{', '.join(metadata['connectors']) if metadata['connectors'] else 'No connectors detected'}

### Code Generation
- Auto-generated elements: {coder.get('generated_count', 'N/A')}
- RAG-sourced generations: {coder.get('rag_sourced', 'N/A')}
- Pure LLM generations: {coder.get('llm_sourced', 'N/A')}
- Errors: {coder.get('error_count', 0)}
{review_section}
{manual_section}

## Risk Assessment

{self._format_risk_areas(metadata['risk_areas'])}

## Token Usage & Cost

| Agent | Tokens |
|-------|--------|
"""
        + "\n".join(
            f"| {agent} | {tokens:,} |"
            for agent, tokens in metadata.get("token_usage", {}).items()
        ) + f"""
| **Total** | **{sum(metadata.get('token_usage', {}).values()):,}** |

Estimated cost: ${metadata.get('total_cost_usd', 0):.4f}

## Recommendations

1. Review all files flagged with `// REVIEW` comments
2. Update application.properties with actual credentials
3. Run the generated test suite and fix failures
4. Add integration tests for external service calls
5. Configure CI/CD pipeline for the Spring Boot application

---
*Generated by MuleSoft-to-SpringBoot Migrator*
"""

    @staticmethod
    def _format_risk_areas(risks: list) -> str:
        if not risks:
            return "No significant risks identified."
        return "\n".join(f"- {risk}" for risk in risks[:15])

    # ------------------------------------------------------------------
    #  OpenAPI enhancements
    # ------------------------------------------------------------------

    def _enhance_openapi(self, generated_files: Dict[str, str]) -> dict:
        """Extract endpoint metadata to enhance Swagger/OpenAPI specs."""
        import re
        enhancements: Dict[str, Any] = {"paths": {}}

        for fp, content in generated_files.items():
            if not ("controller" in fp.lower() or "@RestController" in content):
                continue

            for m in re.finditer(
                r'@(Get|Post|Put|Delete|Patch)Mapping\(\s*["\']?([^"\')\s]+)["\']?\)',
                content,
            ):
                method = m.group(1).lower()
                path = m.group(2)

                # Try to find the method signature
                sig_match = re.search(
                    rf'@{m.group(1)}Mapping.*?\n\s*(?:public\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(',
                    content[m.start():m.start()+500],
                    re.DOTALL,
                )
                return_type = sig_match.group(1) if sig_match else "Object"
                method_name = sig_match.group(2) if sig_match else "unknown"

                enhancements["paths"].setdefault(path, {})[method] = {
                    "operationId": method_name,
                    "summary": f"Auto-migrated from MuleSoft",
                    "returnType": return_type,
                    "sourceFile": fp,
                }

        return enhancements if enhancements["paths"] else {}

    # ------------------------------------------------------------------
    #  Fallback
    # ------------------------------------------------------------------

    def get_fallback(self, context: AgentContext) -> dict:
        """Generate template-based docs without LLM."""
        generated_files = context.get_artifact("generated_files") or {}
        migration_plan = context.get_artifact("migration_plan") or {}
        review_feedback = context.get_artifact("review_feedback") or []
        coder_result = context.get_agent_result("coder") or {}
        test_files = context.get_artifact("test_files") or {}

        metadata = self._collect_metadata(
            context, generated_files, migration_plan, review_feedback,
            coder_result, test_files,
        )
        return {
            "docs": {
                "README.md": self._generate_readme(metadata)[:200] + "...",
                "MIGRATION_REPORT.md": self._generate_migration_report(metadata)[:200] + "...",
            },
            "doc_count": 2,
            "fallback": True,
        }
