"""
ReviewerAgent — reviews generated Spring Boot code per-file.

The reviewer:
  1. Iterates over generated Java files.
  2. Uses RAG to retrieve Spring Boot best practices and anti-patterns.
  3. Scores each file 1-10 with line-specific feedback.
  4. Can trigger a re-review loop (max 2 iterations) when it detects
     the coder should regenerate a file.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import structlog

from api.agents.base import BaseAgent
from api.agents.context import AgentContext
from api.agents.guardrails import AgentGuardrails
from api.agents.result import AgentResult

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
#  Per-file review
# ---------------------------------------------------------------------------

class FileReview:
    """Review result for a single generated file."""

    def __init__(
        self,
        filepath: str,
        score: int = 0,
        feedback: Optional[List[dict]] = None,
        suggestions: Optional[List[str]] = None,
        needs_regen: bool = False,
    ) -> None:
        self.filepath = filepath
        self.score = score  # 1-10
        self.feedback = feedback or []
        # Each feedback item: {line: int|None, severity: str, message: str, suggestion: str}
        self.suggestions = suggestions or []
        self.needs_regen = needs_regen

    def to_dict(self) -> dict:
        return {
            "filepath": self.filepath,
            "score": self.score,
            "feedback": self.feedback,
            "suggestions": self.suggestions,
            "needs_regen": self.needs_regen,
        }


# ---------------------------------------------------------------------------
#  ReviewerAgent
# ---------------------------------------------------------------------------

class ReviewerAgent(BaseAgent):
    """Reviews generated Spring Boot code for quality, correctness, and best practices."""

    name = "reviewer"
    role = "Spring Boot code reviewer and quality expert"
    system_prompt = """You are a senior Spring Boot code reviewer with deep expertise in
Java 17 and Spring Boot 3.2 best practices.

Review the provided Java file and return a JSON object:
{
  "score": <1-10>,
  "feedback": [
    {
      "line": <line_number_or_null>,
      "severity": "critical|warning|info",
      "message": "<what is wrong>",
      "suggestion": "<how to fix>"
    }
  ],
  "suggestions": ["<general improvement suggestions>"],
  "needs_regen": <true if score <= 3 and has critical issues>
}

Scoring guide:
  9-10: Production-ready, follows all best practices
  7-8:  Good quality, minor improvements possible
  5-6:  Functional but has notable issues
  3-4:  Significant problems, needs substantial fixes
  1-2:  Fundamentally broken, needs complete rewrite

Focus on:
- Correctness of Spring Boot annotations and configuration
- Proper error handling and input validation
- Security concerns (injection, hardcoded secrets)
- Performance patterns (N+1 queries, missing @Transactional)
- Missing test scenarios implied by the code
- Java 17 idiom usage

Return ONLY valid JSON. No markdown fences."""

    MAX_REVIEW_ITERATIONS = 2

    # ------------------------------------------------------------------
    #  Core execution
    # ------------------------------------------------------------------

    async def execute(self, context: AgentContext) -> AgentResult:
        """Review all generated files."""
        generated_files: Dict[str, str] = context.get_artifact("generated_files") or {}
        if not generated_files:
            return AgentResult.success(
                output={"reviews": [], "overall_score": 0, "message": "No files to review"},
            )

        reviews: List[dict] = []
        total_tokens = 0
        rag_queries: List[str] = []
        rag_results_used = 0
        files_needing_regen: List[str] = []

        # Review each file
        for filepath, content in generated_files.items():
            if not filepath.endswith((".java", ".properties", ".yml", ".gradle")):
                continue

            review, tokens, rq, rr = await self._review_file(
                context, filepath, content,
            )
            total_tokens += tokens
            rag_queries.extend(rq)
            rag_results_used += rr
            reviews.append(review.to_dict())

            if review.needs_regen:
                files_needing_regen.append(filepath)

        # Calculate overall score
        scores = [r["score"] for r in reviews if r["score"] > 0]
        overall_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        # Store results
        context.set_artifact("review_feedback", reviews)
        context.update(self.name, {
            "overall_score": overall_score,
            "files_reviewed": len(reviews),
            "files_needing_regen": files_needing_regen,
        })

        # Send message to coder if files need regeneration
        if files_needing_regen:
            context.send_message(
                sender=self.name,
                receiver="coder",
                content={
                    "action": "regenerate",
                    "files": files_needing_regen,
                    "reviews": [r for r in reviews if r["filepath"] in files_needing_regen],
                },
                msg_type="request",
            )

        return AgentResult.success(
            output={
                "reviews": reviews,
                "overall_score": overall_score,
                "files_reviewed": len(reviews),
                "files_needing_regen": files_needing_regen,
            },
            token_usage=total_tokens,
            rag_queries=rag_queries,
            rag_results_used=rag_results_used,
        )

    # ------------------------------------------------------------------
    #  Single-file review
    # ------------------------------------------------------------------

    async def _review_file(
        self,
        context: AgentContext,
        filepath: str,
        content: str,
    ) -> tuple[FileReview, int, List[str], int]:
        """Review a single file, with optional re-review.

        Returns:
            (FileReview, tokens_used, rag_queries, rag_results_used)
        """
        total_tokens = 0
        rag_queries: List[str] = []
        rag_results_used = 0

        for iteration in range(1, self.MAX_REVIEW_ITERATIONS + 1):
            # 1. RAG: retrieve best practices
            rag_context = ""
            if self.retriever is not None:
                file_type = self._classify_file(filepath, content)
                query = f"Spring Boot best practices for {file_type}"
                rag_queries.append(query)
                results = await self.query_rag(query, top_k=3)
                if results:
                    rag_results_used += len(results)
                    rag_context = self.format_rag_results(results)

            # 2. Static guardrails check
            guardrail_issues: List[str] = []
            _, syntax_issues = AgentGuardrails.validate_java_syntax(content)
            guardrail_issues.extend(syntax_issues)
            _, ann_issues = AgentGuardrails.validate_spring_annotations(content)
            guardrail_issues.extend(ann_issues)
            security_issues = AgentGuardrails.detect_security_issues(content)
            guardrail_issues.extend(security_issues)

            # 3. Build prompt
            prompt = self._build_review_prompt(
                filepath, content, rag_context, guardrail_issues, iteration,
            )

            # 4. Call LLM
            try:
                response = await self.call_llm_with_retry(prompt)
                total_tokens += len(prompt) // 4 + len(response) // 4
                review_data = self.parse_response(response)

                review = FileReview(
                    filepath=filepath,
                    score=review_data.get("score", 5),
                    feedback=review_data.get("feedback", []),
                    suggestions=review_data.get("suggestions", []),
                    needs_regen=review_data.get("needs_regen", False),
                )

                # Merge guardrail issues into feedback
                for issue in guardrail_issues:
                    review.feedback.append({
                        "line": None,
                        "severity": "warning",
                        "message": f"[Guardrail] {issue}",
                        "suggestion": "Auto-detected by static analysis",
                    })

                # If score is acceptable or we've hit max iterations, stop
                if review.score >= 4 or iteration >= self.MAX_REVIEW_ITERATIONS:
                    return review, total_tokens, rag_queries, rag_results_used

                logger.info(
                    "reviewer.re_review",
                    filepath=filepath,
                    score=review.score,
                    iteration=iteration,
                )

            except Exception as exc:
                logger.warning(
                    "reviewer.llm_failed",
                    filepath=filepath,
                    error=str(exc),
                )
                # Return a guardrails-only review
                return (
                    self._guardrails_only_review(filepath, guardrail_issues),
                    total_tokens,
                    rag_queries,
                    rag_results_used,
                )

        # Should not reach here, but safety net
        return (
            FileReview(filepath=filepath, score=5),
            total_tokens,
            rag_queries,
            rag_results_used,
        )

    # ------------------------------------------------------------------
    #  Prompt helpers
    # ------------------------------------------------------------------

    def _build_review_prompt(
        self,
        filepath: str,
        content: str,
        rag_context: str,
        guardrail_issues: List[str],
        iteration: int,
    ) -> str:
        parts: List[str] = []

        if rag_context:
            parts.append("=== Best practices reference ===")
            parts.append(rag_context)
            parts.append("=== End reference ===\n")

        parts.append(f"Review this generated file: {filepath}")
        if iteration > 1:
            parts.append(f"(Re-review iteration {iteration})")
        parts.append(f"\n```java\n{content[:6000]}\n```")

        if guardrail_issues:
            parts.append("\nStatic analysis already found these issues:")
            for issue in guardrail_issues:
                parts.append(f"  - {issue}")

        parts.append("\nReturn your review as JSON matching the schema described.")
        return "\n".join(parts)

    @staticmethod
    def _classify_file(filepath: str, content: str) -> str:
        """Heuristic file-type classification for RAG query targeting."""
        fp_lower = filepath.lower()
        if "controller" in fp_lower:
            return "REST controller"
        if "service" in fp_lower:
            return "service layer"
        if "repository" in fp_lower:
            return "data repository"
        if "config" in fp_lower or "configuration" in fp_lower:
            return "configuration class"
        if "test" in fp_lower:
            return "test class"
        if fp_lower.endswith(".properties") or fp_lower.endswith(".yml"):
            return "application configuration"
        if "@RestController" in content or "@RequestMapping" in content:
            return "REST controller"
        if "@Service" in content:
            return "service layer"
        return "general Spring Boot component"

    @staticmethod
    def _guardrails_only_review(
        filepath: str, issues: List[str]
    ) -> FileReview:
        """Build a review from guardrails alone when LLM is unavailable."""
        feedback = [
            {
                "line": None,
                "severity": "warning",
                "message": f"[Static] {issue}",
                "suggestion": "Detected by guardrails; LLM review unavailable",
            }
            for issue in issues
        ]
        score = max(1, 8 - len(issues))
        return FileReview(
            filepath=filepath,
            score=score,
            feedback=feedback,
            suggestions=["LLM-based review was unavailable; only static checks ran."],
            needs_regen=score <= 3,
        )

    # ------------------------------------------------------------------
    #  Fallback
    # ------------------------------------------------------------------

    def get_fallback(self, context: AgentContext) -> dict:
        """Return guardrails-only reviews for all files."""
        generated_files = context.get_artifact("generated_files") or {}
        reviews = []
        for filepath, content in generated_files.items():
            if not filepath.endswith(".java"):
                continue
            _, syntax = AgentGuardrails.validate_java_syntax(content)
            security = AgentGuardrails.detect_security_issues(content)
            review = self._guardrails_only_review(filepath, syntax + security)
            reviews.append(review.to_dict())

        scores = [r["score"] for r in reviews if r["score"] > 0]
        return {
            "reviews": reviews,
            "overall_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "files_reviewed": len(reviews),
            "files_needing_regen": [
                r["filepath"] for r in reviews if r.get("needs_regen")
            ],
            "fallback": True,
        }
