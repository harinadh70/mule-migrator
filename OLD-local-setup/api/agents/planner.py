"""
PlannerAgent — analyses MuleSoft XML input and produces a MigrationPlan.

The planner is the first agent in the pipeline.  It:
  1. Parses the XML to extract flows, connectors, and data-weave expressions.
  2. Queries RAG for similar past migrations.
  3. Estimates complexity, risk areas, and the agents needed.
  4. Decides whether the full agentic pipeline is required or a simple
     static conversion is sufficient.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

from api.agents.base import BaseAgent
from api.agents.context import AgentContext
from api.agents.result import AgentResult

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
#  MigrationPlan data-class
# ---------------------------------------------------------------------------

@dataclass
class MigrationPlan:
    """Output of the planner agent."""

    complexity: str = "low"  # low | medium | high | very_high
    complexity_score: int = 0  # 0-100
    flows_detected: int = 0
    connectors_detected: List[str] = field(default_factory=list)
    dataweave_expressions: int = 0
    risk_areas: List[str] = field(default_factory=list)
    estimated_agents_needed: List[str] = field(default_factory=list)
    estimated_tokens: int = 0
    use_full_pipeline: bool = True
    similar_past_migrations: List[dict] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "complexity": self.complexity,
            "complexity_score": self.complexity_score,
            "flows_detected": self.flows_detected,
            "connectors_detected": self.connectors_detected,
            "dataweave_expressions": self.dataweave_expressions,
            "risk_areas": self.risk_areas,
            "estimated_agents_needed": self.estimated_agents_needed,
            "estimated_tokens": self.estimated_tokens,
            "use_full_pipeline": self.use_full_pipeline,
            "similar_past_migrations": self.similar_past_migrations,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
#  Known connector namespaces
# ---------------------------------------------------------------------------
KNOWN_SIMPLE_CONNECTORS = frozenset({
    "http", "https", "logger", "set-payload", "set-variable",
    "flow-ref", "choice", "foreach", "scatter-gather",
    "try", "error-handler", "on-error-propagate", "on-error-continue",
})

HIGH_RISK_CONNECTORS = frozenset({
    "salesforce", "sap", "workday", "servicenow",
    "mq", "jms", "amqp", "vm", "kafka",
    "batch", "poll", "watermark",
    "objectstore", "cache",
})


# ---------------------------------------------------------------------------
#  PlannerAgent
# ---------------------------------------------------------------------------

class PlannerAgent(BaseAgent):
    """Analyses MuleSoft input and creates a migration plan."""

    name = "planner"
    role = "migration planning expert"
    system_prompt = """You are a senior migration architect specializing in MuleSoft-to-Spring Boot conversions.

Given a MuleSoft XML application, analyse its structure and produce a migration plan in JSON:
{
  "complexity": "low|medium|high|very_high",
  "complexity_score": <0-100>,
  "risk_areas": ["<description of each risk>"],
  "recommended_approach": "<brief strategy>",
  "notes": "<any special observations>"
}

Consider:
- Number and nesting depth of flows
- Connector types (HTTP is simple; SAP/Salesforce are complex)
- DataWeave expression complexity
- Error handling patterns
- Transaction boundaries
- Custom Java components

Return ONLY valid JSON."""

    # ------------------------------------------------------------------
    #  Core execution
    # ------------------------------------------------------------------

    async def execute(self, context: AgentContext) -> AgentResult:
        """Analyse the input XML and produce a MigrationPlan."""
        xml_files: Dict[str, str] = context.get_artifact("xml_files") or {}
        if not xml_files:
            return AgentResult.from_error("No XML files provided to planner")

        # --- Step 1: static analysis ---------------------------------
        plan = self._static_analysis(xml_files)

        # --- Step 2: RAG lookup for similar migrations ---------------
        rag_queries: List[str] = []
        rag_results_used = 0

        if self.retriever is not None:
            for connector in plan.connectors_detected[:5]:
                query = f"MuleSoft {connector} connector migration to Spring Boot"
                rag_queries.append(query)
                results = await self.query_rag(query, top_k=3)
                if results:
                    rag_results_used += len(results)
                    plan.similar_past_migrations.extend(
                        {"connector": connector, "result": r}
                        for r in results[:2]
                    )

        # --- Step 3: LLM-enhanced analysis (optional) ----------------
        token_usage = 0
        if plan.complexity in ("high", "very_high") and self.llm_provider is not None:
            try:
                combined_xml = "\n".join(
                    f"<!-- {name} -->\n{content[:3000]}"
                    for name, content in list(xml_files.items())[:3]
                )
                rag_context = self.format_rag_results(
                    [r.get("result", {}) for r in plan.similar_past_migrations[:3]]
                )
                prompt = self.build_prompt(context, rag_context)
                prompt += f"\n\nMuleSoft XML to analyse:\n{combined_xml[:6000]}"

                response = await self.call_llm_with_retry(prompt)
                llm_analysis = self.parse_response(response)
                token_usage = len(prompt) // 4 + len(response) // 4

                # Merge LLM insights into plan
                if "risk_areas" in llm_analysis:
                    plan.risk_areas.extend(llm_analysis["risk_areas"])
                if "notes" in llm_analysis:
                    plan.notes = llm_analysis.get("notes", "")
                if "complexity" in llm_analysis:
                    plan.complexity = llm_analysis["complexity"]
                if "complexity_score" in llm_analysis:
                    plan.complexity_score = llm_analysis["complexity_score"]
            except Exception as exc:
                logger.warning("planner.llm_analysis.failed", error=str(exc))
                plan.notes += f" (LLM analysis unavailable: {exc})"

        # --- Step 4: decide pipeline depth ---------------------------
        plan.estimated_agents_needed = self._decide_agents(plan)
        plan.estimated_tokens = self._estimate_tokens(plan, xml_files)
        plan.use_full_pipeline = plan.complexity in ("high", "very_high") or len(plan.connectors_detected) > 3

        # Store plan as artifact
        context.set_artifact("migration_plan", plan.to_dict())
        context.update(self.name, plan.to_dict())

        return AgentResult.success(
            output=plan.to_dict(),
            token_usage=token_usage,
            rag_queries=rag_queries,
            rag_results_used=rag_results_used,
        )

    # ------------------------------------------------------------------
    #  Static XML analysis
    # ------------------------------------------------------------------

    def _static_analysis(self, xml_files: Dict[str, str]) -> MigrationPlan:
        """Extract structural information from the raw XML without LLM."""
        plan = MigrationPlan()
        all_connectors: set[str] = set()
        dw_count = 0
        flow_count = 0
        risk_areas: List[str] = []

        for filename, xml_str in xml_files.items():
            try:
                root = ET.fromstring(xml_str)
            except ET.ParseError:
                risk_areas.append(f"Unparseable XML: {filename}")
                continue

            # Count flows
            flows = root.findall(".//{http://www.mulesoft.org/schema/mule/core}flow")
            flows += root.findall(".//flow")
            flow_count += len(flows)

            # Detect connectors by namespace prefix
            for elem in root.iter():
                tag = elem.tag
                if "}" in tag:
                    ns = tag.split("}")[0].strip("{")
                    local = tag.split("}")[-1]
                    # Extract connector name from namespace
                    ns_parts = ns.split("/")
                    if len(ns_parts) > 1:
                        connector = ns_parts[-1]
                        if connector not in ("core", "mule", "xml", "spring"):
                            all_connectors.add(connector)

                # DataWeave expressions
                for attr_val in elem.attrib.values():
                    if attr_val.startswith("#[") or "dw:" in attr_val.lower():
                        dw_count += 1
                if elem.text and ("%dw" in (elem.text or "") or "#[" in (elem.text or "")):
                    dw_count += 1

            # Check for high-risk patterns
            xml_lower = xml_str.lower()
            if "batch:" in xml_lower or "batch-job" in xml_lower:
                risk_areas.append(f"Batch processing detected in {filename}")
            if "transactional" in xml_lower:
                risk_areas.append(f"Transaction boundaries in {filename}")
            if "security:" in xml_lower or "oauth" in xml_lower:
                risk_areas.append(f"Security configuration in {filename}")

        # Detect high-risk connectors
        for conn in all_connectors:
            if conn in HIGH_RISK_CONNECTORS:
                risk_areas.append(f"Complex connector: {conn}")

        plan.flows_detected = flow_count
        plan.connectors_detected = sorted(all_connectors)
        plan.dataweave_expressions = dw_count
        plan.risk_areas = risk_areas

        # Calculate complexity score
        score = 0
        score += min(flow_count * 5, 30)
        score += min(len(all_connectors) * 8, 30)
        score += min(dw_count * 3, 20)
        score += min(len(risk_areas) * 5, 20)
        plan.complexity_score = min(score, 100)

        if score <= 20:
            plan.complexity = "low"
        elif score <= 45:
            plan.complexity = "medium"
        elif score <= 70:
            plan.complexity = "high"
        else:
            plan.complexity = "very_high"

        return plan

    # ------------------------------------------------------------------
    #  Pipeline decisions
    # ------------------------------------------------------------------

    def _decide_agents(self, plan: MigrationPlan) -> List[str]:
        """Determine which agents are needed based on the plan."""
        agents = ["planner", "coder"]

        if plan.complexity in ("high", "very_high"):
            agents.append("reviewer")

        if plan.flows_detected > 0:
            agents.append("tester")

        agents.append("docs")
        return agents

    def _estimate_tokens(
        self, plan: MigrationPlan, xml_files: Dict[str, str]
    ) -> int:
        """Rough token estimate for the full pipeline."""
        total_chars = sum(len(v) for v in xml_files.values())
        base_tokens = total_chars // 4  # input tokens

        # Each agent adds overhead
        agent_overhead = len(plan.estimated_agents_needed) * 2000
        connector_overhead = len(plan.connectors_detected) * 1500
        dw_overhead = plan.dataweave_expressions * 500

        return base_tokens + agent_overhead + connector_overhead + dw_overhead

    # ------------------------------------------------------------------
    #  Fallback
    # ------------------------------------------------------------------

    def get_fallback(self, context: AgentContext) -> dict:
        """Return a minimal plan when the LLM is unavailable."""
        xml_files = context.get_artifact("xml_files") or {}
        plan = self._static_analysis(xml_files)
        plan.notes = "Generated via static analysis only (LLM unavailable)"
        plan.estimated_agents_needed = ["coder", "docs"]
        plan.use_full_pipeline = False
        return plan.to_dict()
