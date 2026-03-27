"""
Agent framework for the MuleSoft-to-SpringBoot Agentic AI migration platform.

This package provides a multi-agent pipeline that orchestrates LLM-powered
code generation, review, testing, and documentation for MuleSoft-to-Spring Boot
migrations.  It builds on the existing static converters in
``backend.migrator`` and augments them with RAG-enhanced LLM agents.

Pipeline stages:
    Planner -> Static Engine -> Coder -> Reviewer <-> Coder (loop) -> Tester + Docs (parallel)

Quick start::

    from api.agents import PipelineOrchestrator

    orchestrator = PipelineOrchestrator(
        llm_config={"provider": "anthropic", "apiKey": "sk-...", "model": "claude-sonnet-4-20250514"},
    )
    context = await orchestrator.run(xml_files={"flow.xml": xml_content})
    trace = context.to_trace()
"""

# Context & result
from api.agents.context import AgentContext, AgentTrace, AgentMessage
from api.agents.result import AgentResult

# Base agent
from api.agents.base import BaseAgent

# Infrastructure
from api.agents.memory import AgentMemory
from api.agents.guardrails import AgentGuardrails
from api.agents.tools import AgentTools, Tool

# Concrete agents
from api.agents.planner import PlannerAgent, MigrationPlan
from api.agents.coder import CoderAgent
from api.agents.reviewer import ReviewerAgent, FileReview
from api.agents.tester import TesterAgent
from api.agents.docs import DocsAgent

# Orchestrator
from api.agents.orchestrator import PipelineOrchestrator

__all__ = [
    # Context & result
    "AgentContext",
    "AgentTrace",
    "AgentMessage",
    "AgentResult",
    # Base agent
    "BaseAgent",
    # Infrastructure
    "AgentMemory",
    "AgentGuardrails",
    "AgentTools",
    "Tool",
    # Concrete agents
    "PlannerAgent",
    "MigrationPlan",
    "CoderAgent",
    "ReviewerAgent",
    "FileReview",
    "TesterAgent",
    "DocsAgent",
    # Orchestrator
    "PipelineOrchestrator",
]
