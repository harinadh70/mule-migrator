"""
PipelineOrchestrator — DAG-based execution engine for the agentic migration pipeline.

Coordinates all agents (Planner -> Static Engine -> Coder -> Reviewer -> Tester/Docs)
with production-grade reliability features:

  - DAG-based execution with topological ordering and parallel level dispatch
  - Circuit breaker per agent (configurable failure threshold, default 3)
  - Global timeout enforcement (default 10 minutes)
  - Checkpoint/resume after each agent (in-memory + optional disk persistence)
  - Parallel execution of independent agents (tester + docs)
  - Cumulative cost and token tracking across all agents
  - Dry-run mode for plan-only execution
  - Real-time progress via sync/async callback event system
  - Reviewer -> Coder feedback loop with configurable max iterations
  - Integration with AgentMemory for cross-run learning
  - Integration with the existing static migration engine (parser, flow_converter, etc.)
  - Cancellation support
"""

from __future__ import annotations

import asyncio
import enum
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Set,
    TYPE_CHECKING,
)

import structlog

from api.agents.base import BaseAgent
from api.agents.context import AgentContext
from api.agents.result import AgentResult
from api.agents.planner import PlannerAgent
from api.agents.coder import CoderAgent
from api.agents.reviewer import ReviewerAgent
from api.agents.tester import TesterAgent
from api.agents.docs import DocsAgent
from api.agents.memory import AgentMemory

if TYPE_CHECKING:
    from backend.migrator.llm_validator import BaseLLMProvider
    from api.rag.retriever import HybridRetriever

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

DEFAULT_GLOBAL_TIMEOUT_S = 600          # 10 minutes
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 3
DEFAULT_COST_PER_1K_TOKENS = 0.005      # blended input+output average

PIPELINE_STAGES = [
    "planner",
    "static_engine",
    "coder",
    "reviewer",
    "tester",
    "docs",
]


# ---------------------------------------------------------------------------
#  Enumerations
# ---------------------------------------------------------------------------

class PipelineStatus(str, enum.Enum):
    """Overall pipeline run status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    DRY_RUN = "dry_run"


class EventType(str, enum.Enum):
    """Event types emitted to progress callbacks."""
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    AGENT_SKIPPED = "agent_skipped"
    AGENT_BYPASSED = "agent_bypassed"
    CHECKPOINT_SAVED = "checkpoint_saved"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    PARALLEL_GROUP_STARTED = "parallel_group_started"
    PARALLEL_GROUP_COMPLETED = "parallel_group_completed"
    PROGRESS_UPDATE = "progress_update"
    REVIEW_LOOP_STARTED = "review_loop_started"
    REVIEW_LOOP_COMPLETED = "review_loop_completed"
    STATIC_ENGINE_STARTED = "static_engine_started"
    STATIC_ENGINE_COMPLETED = "static_engine_completed"


# ---------------------------------------------------------------------------
#  Supporting data-classes
# ---------------------------------------------------------------------------

@dataclass
class PipelineEvent:
    """A single event emitted by the orchestrator."""

    event_type: EventType
    agent_name: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "agent_name": self.agent_name,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass
class CircuitBreakerState:
    """Per-agent circuit breaker state."""

    failure_count: int = 0
    is_open: bool = False
    last_failure_at: Optional[float] = None
    last_error: Optional[str] = None

    def record_failure(self, error: str, threshold: int) -> None:
        self.failure_count += 1
        self.last_failure_at = time.monotonic()
        self.last_error = error
        if self.failure_count >= threshold:
            self.is_open = True

    def record_success(self) -> None:
        self.failure_count = 0
        self.is_open = False
        self.last_failure_at = None
        self.last_error = None


@dataclass
class DAGNode:
    """A node in the execution DAG."""

    name: str
    agent: Optional[BaseAgent] = None       # None for pseudo-nodes (static_engine)
    dependencies: FrozenSet[str] = field(default_factory=frozenset)

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DAGNode):
            return NotImplemented
        return self.name == other.name


@dataclass
class PipelineConfig:
    """Tuning knobs for the orchestrator."""

    global_timeout_s: int = DEFAULT_GLOBAL_TIMEOUT_S
    circuit_breaker_threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD
    cost_per_1k_tokens: float = DEFAULT_COST_PER_1K_TOKENS
    dry_run: bool = False
    checkpoint_dir: Optional[str] = None
    skip_agents: List[str] = field(default_factory=list)
    enable_review_loop: bool = True
    max_review_loops: int = 2


@dataclass
class PipelineReport:
    """Final report produced at the end of a pipeline run."""

    run_id: str = ""
    status: PipelineStatus = PipelineStatus.PENDING
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: int = 0
    agents_executed: List[str] = field(default_factory=list)
    agents_skipped: List[str] = field(default_factory=list)
    agents_bypassed: List[str] = field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    agent_results: Dict[str, dict] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    events: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "agents_executed": self.agents_executed,
            "agents_skipped": self.agents_skipped,
            "agents_bypassed": self.agents_bypassed,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "agent_results": self.agent_results,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
#  Callback protocol
# ---------------------------------------------------------------------------

# A callback receives a PipelineEvent; it may be sync or async.
ProgressCallback = Callable[[PipelineEvent], Any]


# ---------------------------------------------------------------------------
#  Backward-compatible ProgressTracker (kept for API consumers)
# ---------------------------------------------------------------------------

class ProgressTracker:
    """Lightweight tracker that wraps the event system for simple % queries."""

    def __init__(
        self,
        stages: List[str],
        event_callback: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self._stages = stages
        self._current_index = 0
        self._current_stage: Optional[str] = None
        self._event_callback = event_callback
        self._start_time = time.monotonic()

    @property
    def percentage(self) -> int:
        if not self._stages:
            return 100
        return int((self._current_index / len(self._stages)) * 100)

    @property
    def current_agent(self) -> Optional[str]:
        return self._current_stage

    def start_stage(self, stage: str) -> None:
        self._current_stage = stage
        if stage in self._stages:
            self._current_index = self._stages.index(stage)
        self._emit({
            "type": "agent_started",
            "agent": stage,
            "progress": self.percentage,
            "elapsed_ms": int((time.monotonic() - self._start_time) * 1000),
        })

    def finish_stage(self, stage: str, status: str) -> None:
        if stage in self._stages:
            self._current_index = self._stages.index(stage) + 1
        self._emit({
            "type": "agent_finished",
            "agent": stage,
            "status": status,
            "progress": self.percentage,
            "elapsed_ms": int((time.monotonic() - self._start_time) * 1000),
        })

    def complete(self) -> None:
        self._current_index = len(self._stages)
        self._emit({
            "type": "pipeline_complete",
            "progress": 100,
            "elapsed_ms": int((time.monotonic() - self._start_time) * 1000),
        })

    def _emit(self, event: dict) -> None:
        logger.info("pipeline.event", **event)
        if self._event_callback:
            try:
                self._event_callback(event)
            except Exception as exc:
                logger.warning("pipeline.event_callback.failed", error=str(exc))


# ---------------------------------------------------------------------------
#  CircuitBreaker (registry facade)
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Per-agent circuit breaker registry.

    After *threshold* consecutive failures for a given agent, the breaker
    trips and all subsequent calls are bypassed with a fallback until a
    manual reset or a successful execution.
    """

    def __init__(self, threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD) -> None:
        self.threshold = threshold
        self._states: Dict[str, CircuitBreakerState] = defaultdict(CircuitBreakerState)

    def record_success(self, agent_name: str) -> None:
        self._states[agent_name].record_success()

    def record_failure(self, agent_name: str, error: str = "") -> None:
        self._states[agent_name].record_failure(error, self.threshold)

    def is_open(self, agent_name: str) -> bool:
        return self._states[agent_name].is_open

    def get_state(self, agent_name: str) -> CircuitBreakerState:
        return self._states[agent_name]

    def reset(self, agent_name: str) -> None:
        self._states[agent_name].record_success()

    def reset_all(self) -> None:
        self._states.clear()

    def to_dict(self) -> Dict[str, dict]:
        return {
            name: {
                "failure_count": st.failure_count,
                "is_open": st.is_open,
                "last_error": st.last_error,
            }
            for name, st in self._states.items()
        }


# ---------------------------------------------------------------------------
#  PipelineOrchestrator
# ---------------------------------------------------------------------------

class PipelineOrchestrator:
    """DAG-based orchestrator that drives the full migration pipeline.

    Supports two calling conventions for backward compatibility:

    **Legacy (positional context built internally)**::

        orchestrator = PipelineOrchestrator(
            llm_config={"provider": "anthropic", "apiKey": "...", "model": "..."},
        )
        context = await orchestrator.run(xml_files={"flow.xml": "<mule>...</mule>"})
        print(context.to_trace())

    **New (explicit context, returns a PipelineReport)**::

        orchestrator = PipelineOrchestrator(
            llm_config=llm_config,
            pipeline_config=PipelineConfig(dry_run=True),
        )
        report = await orchestrator.run_pipeline(context)
    """

    # ------------------------------------------------------------------
    #  Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        llm_config: Optional[dict] = None,
        llm_provider: Optional["BaseLLMProvider"] = None,
        retriever: Optional["HybridRetriever"] = None,
        memory: Optional[AgentMemory] = None,
        *,
        global_timeout_seconds: int = DEFAULT_GLOBAL_TIMEOUT_S,
        max_review_loops: int = 2,
        event_callback: Optional[Callable[[dict], None]] = None,
        pipeline_config: Optional[PipelineConfig] = None,
        progress_callbacks: Optional[List[ProgressCallback]] = None,
    ) -> None:
        self._llm_config = llm_config or {}
        self._llm_provider = llm_provider
        self._retriever = retriever
        self._memory = memory or AgentMemory()
        self._global_timeout = global_timeout_seconds
        self._max_review_loops = max_review_loops
        self._event_callback = event_callback

        # New-style config (takes precedence when supplied)
        self.config = pipeline_config or PipelineConfig(
            global_timeout_s=global_timeout_seconds,
            max_review_loops=max_review_loops,
        )

        # Callback registries
        self._callbacks: List[ProgressCallback] = list(progress_callbacks or [])

        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(
            threshold=self.config.circuit_breaker_threshold,
        )

        # Progress tracker (legacy interface)
        self._progress: Optional[ProgressTracker] = None

        # Event log
        self._events: List[PipelineEvent] = []

        # Cancellation flag
        self._cancelled = False

        # Instantiate agents
        agent_kwargs: Dict[str, Any] = dict(
            llm_provider=llm_provider,
            llm_config=llm_config,
            retriever=retriever,
        )
        self._planner = PlannerAgent(**agent_kwargs)
        self._coder = CoderAgent(**agent_kwargs)
        self._reviewer = ReviewerAgent(**agent_kwargs)
        self._tester = TesterAgent(**agent_kwargs)
        self._docs = DocsAgent(**agent_kwargs)

        # Agent registry (name -> instance)
        self._agents: Dict[str, BaseAgent] = {
            "planner": self._planner,
            "coder": self._coder,
            "reviewer": self._reviewer,
            "tester": self._tester,
            "docs": self._docs,
        }

        # DAG definition
        self._dag: Dict[str, DAGNode] = {}
        self._build_default_dag()

    # ------------------------------------------------------------------
    #  DAG construction
    # ------------------------------------------------------------------

    def _build_default_dag(self) -> None:
        """Wire up the default execution graph.

        ::

            planner
               |
          static_engine
               |
            coder
               |
           reviewer
            /     \\
         tester   docs

        ``tester`` and ``docs`` both depend only on ``reviewer`` and thus
        execute in parallel.
        """
        self._dag = {
            "planner": DAGNode(
                name="planner",
                agent=self._planner,
                dependencies=frozenset(),
            ),
            "static_engine": DAGNode(
                name="static_engine",
                agent=None,  # pseudo-node handled specially
                dependencies=frozenset({"planner"}),
            ),
            "coder": DAGNode(
                name="coder",
                agent=self._coder,
                dependencies=frozenset({"static_engine"}),
            ),
            "reviewer": DAGNode(
                name="reviewer",
                agent=self._reviewer,
                dependencies=frozenset({"coder"}),
            ),
            "tester": DAGNode(
                name="tester",
                agent=self._tester,
                dependencies=frozenset({"reviewer"}),
            ),
            "docs": DAGNode(
                name="docs",
                agent=self._docs,
                dependencies=frozenset({"reviewer"}),
            ),
        }

    # ------------------------------------------------------------------
    #  Public API: agent registration
    # ------------------------------------------------------------------

    def register_agent(
        self,
        name: str,
        agent: BaseAgent,
        dependencies: Optional[Set[str]] = None,
    ) -> None:
        """Register a custom agent and insert it into the DAG.

        Args:
            name: Unique identifier for the agent node.
            agent: A ``BaseAgent`` sub-class instance.
            dependencies: Agent names that must complete first.
        """
        self._agents[name] = agent
        self._dag[name] = DAGNode(
            name=name,
            agent=agent,
            dependencies=frozenset(dependencies or set()),
        )
        logger.info("orchestrator.agent_registered", name=name)

    def remove_agent(self, name: str) -> None:
        """Remove an agent from the DAG (and prune from others' deps)."""
        self._dag.pop(name, None)
        self._agents.pop(name, None)
        for node in self._dag.values():
            if name in node.dependencies:
                node.dependencies = node.dependencies - {name}

    def add_progress_callback(self, callback: ProgressCallback) -> None:
        """Register an additional progress callback (sync or async)."""
        self._callbacks.append(callback)

    def cancel(self) -> None:
        """Request cancellation of the running pipeline."""
        self._cancelled = True
        logger.info("orchestrator.cancel_requested")

    # ------------------------------------------------------------------
    #  Public API: legacy ``run`` (returns AgentContext)
    # ------------------------------------------------------------------

    async def run(
        self,
        xml_files: Dict[str, str],
        config: Optional[dict] = None,
    ) -> AgentContext:
        """Execute the full migration pipeline (legacy interface).

        Args:
            xml_files: Mapping of filename -> XML content.
            config: Optional configuration overrides.

        Returns:
            A fully-populated ``AgentContext`` with all results and traces.
        """
        config = config or {}

        context = AgentContext(
            enabled=True,
            llm_config=self._llm_config,
        )
        context.set_artifact("xml_files", xml_files)
        context.set_artifact("config", config)

        stages = list(PIPELINE_STAGES)
        self._progress = ProgressTracker(stages, self._event_callback)

        try:
            await asyncio.wait_for(
                self._execute_pipeline(context),
                timeout=self.config.global_timeout_s,
            )
        except asyncio.TimeoutError:
            logger.error(
                "pipeline.global_timeout",
                run_id=context.id,
                timeout=self.config.global_timeout_s,
            )
            context.send_message(
                sender="orchestrator",
                receiver="*",
                content=f"Pipeline timed out after {self.config.global_timeout_s}s",
                msg_type="warning",
            )
        except asyncio.CancelledError:
            logger.warning("pipeline.cancelled", run_id=context.id)
        except Exception as exc:
            logger.error(
                "pipeline.fatal_error",
                run_id=context.id,
                error=str(exc),
                exc_info=True,
            )

        self._progress.complete()

        # Persist to memory
        final_result = AgentResult.success(output=context.pipeline_state)
        self._memory.store(context, final_result)

        return context

    # ------------------------------------------------------------------
    #  Public API: new ``run_pipeline`` (returns PipelineReport)
    # ------------------------------------------------------------------

    async def run_pipeline(self, context: AgentContext) -> PipelineReport:
        """Execute the full pipeline and return a structured report.

        This is the preferred entry-point for new code.  It returns a
        ``PipelineReport`` with full cost/token/event tracking.
        """
        self._cancelled = False
        self._events.clear()

        report = PipelineReport(run_id=context.id)
        report.started_at = datetime.now(timezone.utc).isoformat()
        pipeline_start = time.monotonic()

        await self._emit_event(EventType.PIPELINE_STARTED, data={
            "run_id": context.id,
            "dry_run": self.config.dry_run,
            "agents": list(self._dag.keys()),
        })

        stages = list(PIPELINE_STAGES)
        self._progress = ProgressTracker(stages, self._event_callback)

        try:
            await asyncio.wait_for(
                self._execute_dag(context, report),
                timeout=self.config.global_timeout_s,
            )
        except asyncio.TimeoutError:
            report.status = PipelineStatus.TIMED_OUT
            report.errors.append(
                f"Pipeline timed out after {self.config.global_timeout_s}s"
            )
            logger.error(
                "orchestrator.global_timeout",
                run_id=context.id,
                timeout_s=self.config.global_timeout_s,
            )
            await self._emit_event(EventType.PIPELINE_FAILED, data={
                "reason": "global_timeout",
                "timeout_s": self.config.global_timeout_s,
            })
        except asyncio.CancelledError:
            report.status = PipelineStatus.CANCELLED
            report.errors.append("Pipeline was cancelled")
            await self._emit_event(EventType.PIPELINE_FAILED, data={
                "reason": "cancelled",
            })
        except Exception as exc:
            report.status = PipelineStatus.FAILED
            report.errors.append(f"Unexpected pipeline error: {exc}")
            logger.error(
                "orchestrator.unexpected_error",
                run_id=context.id,
                error=str(exc),
                exc_info=True,
            )
            await self._emit_event(EventType.PIPELINE_FAILED, data={
                "reason": "unexpected_error",
                "error": str(exc),
            })

        # Finalise report
        report.duration_ms = int((time.monotonic() - pipeline_start) * 1000)
        report.finished_at = datetime.now(timezone.utc).isoformat()
        report.total_tokens = sum(context.token_usage.values())
        report.total_cost_usd = (
            report.total_tokens / 1000.0 * self.config.cost_per_1k_tokens
        )
        context.total_cost_usd = report.total_cost_usd
        report.events = [e.to_dict() for e in self._events]

        if self._progress:
            self._progress.complete()

        # Determine overall status when not already set by an error path
        if report.status == PipelineStatus.PENDING:
            report.status = self._determine_final_status(report)

        # Persist to memory
        self._persist_to_memory(context, report)

        await self._emit_event(EventType.PIPELINE_COMPLETED, data=report.to_dict())

        logger.info(
            "orchestrator.pipeline_complete",
            run_id=context.id,
            status=report.status.value,
            duration_ms=report.duration_ms,
            total_tokens=report.total_tokens,
            total_cost_usd=round(report.total_cost_usd, 6),
            agents_executed=report.agents_executed,
        )

        return report

    # ------------------------------------------------------------------
    #  Public API: dry run
    # ------------------------------------------------------------------

    async def dry_run(self, context: AgentContext) -> PipelineReport:
        """Execute only the planner to preview the execution plan.

        No code is generated, reviewed, or tested.
        """
        saved = self.config.dry_run
        self.config.dry_run = True
        try:
            report = await self.run_pipeline(context)
        finally:
            self.config.dry_run = saved

        # Enrich report with execution plan details
        execution_order = self._topological_sort()
        migration_plan = context.get_artifact("migration_plan") or {}
        report.agent_results["_dry_run_plan"] = {
            "execution_order": execution_order,
            "estimated_agents": migration_plan.get(
                "estimated_agents_needed", list(self._dag.keys()),
            ),
            "dag": {
                name: sorted(node.dependencies)
                for name, node in self._dag.items()
            },
            "migration_plan": migration_plan,
            "config": {
                "global_timeout_s": self.config.global_timeout_s,
                "circuit_breaker_threshold": self.config.circuit_breaker_threshold,
                "cost_per_1k_tokens": self.config.cost_per_1k_tokens,
                "skip_agents": self.config.skip_agents,
            },
        }
        report.status = PipelineStatus.DRY_RUN
        return report

    # ------------------------------------------------------------------
    #  Public API: resume from checkpoint
    # ------------------------------------------------------------------

    async def resume(
        self,
        context: AgentContext,
        from_agent: Optional[str] = None,
    ) -> PipelineReport:
        """Resume a previously-checkpointed pipeline run.

        If *from_agent* is given, execution restarts from that agent
        (its checkpoint is restored first).  Otherwise the orchestrator
        finds the last successfully-completed agent and resumes after it.
        """
        if from_agent:
            restored = context.restore_checkpoint(from_agent)
            if restored:
                await self._emit_event(
                    EventType.CHECKPOINT_RESTORED, agent_name=from_agent,
                )
            else:
                logger.warning(
                    "orchestrator.no_checkpoint",
                    agent=from_agent,
                    run_id=context.id,
                )
        else:
            execution_order = self._topological_sort()
            resume_point = self._find_resume_point(context, execution_order)
            if resume_point:
                context.restore_checkpoint(resume_point)
                await self._emit_event(
                    EventType.CHECKPOINT_RESTORED, agent_name=resume_point,
                )

        logger.info(
            "orchestrator.resuming",
            run_id=context.id,
            from_agent=from_agent,
        )
        return await self.run_pipeline(context)

    # ------------------------------------------------------------------
    #  Public API: introspection
    # ------------------------------------------------------------------

    def get_progress(self) -> dict:
        """Return current pipeline progress for API consumers."""
        if self._progress is None:
            return {"current_agent": None, "progress": 0}
        return {
            "current_agent": self._progress.current_agent,
            "progress": self._progress.percentage,
        }

    def get_dag_description(self) -> Dict[str, Any]:
        """Return a JSON-serialisable description of the current DAG."""
        topo = self._topological_sort()
        return {
            "nodes": {
                name: {
                    "agent_class": (
                        type(node.agent).__name__ if node.agent else "static_engine"
                    ),
                    "dependencies": sorted(node.dependencies),
                }
                for name, node in self._dag.items()
            },
            "execution_order": topo,
            "levels": self._compute_dag_levels(topo),
        }

    def get_circuit_breaker_states(self) -> Dict[str, dict]:
        """Return current circuit breaker state for all agents."""
        return self._circuit_breaker.to_dict()

    @property
    def events(self) -> List[PipelineEvent]:
        """Read-only access to the accumulated event log."""
        return list(self._events)

    # ------------------------------------------------------------------
    #  DAG execution engine (new-style)
    # ------------------------------------------------------------------

    async def _execute_dag(
        self,
        context: AgentContext,
        report: PipelineReport,
    ) -> None:
        """Walk the DAG in topological order, running parallel groups together."""
        execution_order = self._topological_sort()
        completed: Set[str] = set()

        levels = self._compute_dag_levels(execution_order)

        for level_agents in levels:
            if self._cancelled:
                report.errors.append("Pipeline cancelled by user")
                return

            to_run = [
                name for name in level_agents
                if name not in completed
                and self._should_run_agent(name, context)
            ]

            skipped = [
                name for name in level_agents
                if name not in completed
                and not self._should_run_agent(name, context)
            ]
            for s in skipped:
                report.agents_skipped.append(s)
                await self._emit_event(EventType.AGENT_SKIPPED, agent_name=s)

            if not to_run:
                completed.update(level_agents)
                continue

            if len(to_run) == 1:
                await self._run_dag_node(to_run[0], context, report)
                completed.add(to_run[0])
            else:
                # Parallel group
                await self._emit_event(
                    EventType.PARALLEL_GROUP_STARTED,
                    data={"agents": to_run},
                )
                tasks = [
                    self._run_dag_node(name, context, report)
                    for name in to_run
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                completed.update(to_run)
                await self._emit_event(
                    EventType.PARALLEL_GROUP_COMPLETED,
                    data={"agents": to_run},
                )

            # Progress
            total = len(self._dag)
            done = len(completed)
            await self._emit_event(EventType.PROGRESS_UPDATE, data={
                "completed": done,
                "total": total,
                "percent": round(done / total * 100, 1) if total else 0,
            })

        # Reviewer -> Coder feedback loop (post-DAG)
        if self.config.enable_review_loop and not self.config.dry_run:
            await self._review_feedback_loop(context, report)

    async def _run_dag_node(
        self,
        name: str,
        context: AgentContext,
        report: PipelineReport,
    ) -> None:
        """Dispatch a single DAG node (agent or static engine)."""
        node = self._dag.get(name)
        if node is None:
            return

        # Static engine is a special pseudo-node
        if name == "static_engine":
            await self._run_static_engine(context)
            report.agents_executed.append("static_engine")
            self._save_checkpoint(context, "static_engine")
            await self._emit_event(EventType.CHECKPOINT_SAVED, agent_name="static_engine")
            return

        if node.agent is None:
            logger.warning("orchestrator.no_agent_for_node", node=name)
            return

        # Circuit breaker check
        if self._circuit_breaker.is_open(name):
            logger.warning(
                "orchestrator.circuit_breaker_open",
                agent=name,
                failures=self._circuit_breaker.get_state(name).failure_count,
            )
            await self._emit_event(EventType.AGENT_BYPASSED, agent_name=name, data={
                "reason": "circuit_breaker_open",
                "failure_count": self._circuit_breaker.get_state(name).failure_count,
                "last_error": self._circuit_breaker.get_state(name).last_error,
            })
            report.agents_bypassed.append(name)
            try:
                fallback_output = node.agent.get_fallback(context)
                context.update(name, fallback_output)
                report.agent_results[name] = {
                    "status": "bypassed",
                    "fallback_used": True,
                    "output": fallback_output,
                }
            except Exception as fb_exc:
                report.errors.append(
                    f"Agent '{name}' bypassed and fallback failed: {fb_exc}"
                )
            if self._progress:
                self._progress.start_stage(name)
                self._progress.finish_stage(name, "bypassed")
            return

        # Normal execution
        result = await self._execute_agent(name, node.agent, context, report)

        # Update circuit breaker
        if result is not None and result.is_usable:
            self._circuit_breaker.record_success(name)
        elif result is not None:
            self._circuit_breaker.record_failure(name, result.error or "unknown")

        # Checkpoint
        self._save_checkpoint(context, name)
        await self._emit_event(EventType.CHECKPOINT_SAVED, agent_name=name)

    async def _execute_agent(
        self,
        name: str,
        agent: BaseAgent,
        context: AgentContext,
        report: PipelineReport,
    ) -> Optional[AgentResult]:
        """Call ``agent.safe_execute()`` with full tracking."""
        if self._progress:
            self._progress.start_stage(name)

        await self._emit_event(EventType.AGENT_STARTED, agent_name=name)
        logger.info("orchestrator.agent_started", agent=name, run_id=context.id)

        try:
            result = await agent.safe_execute(context)
        except Exception as exc:
            logger.error(
                "orchestrator.agent_crashed",
                agent=name,
                error=str(exc),
                exc_info=True,
            )
            result = AgentResult.from_error(error=str(exc))

        # Record
        report.agent_results[name] = result.to_dict()
        report.agents_executed.append(name)

        if result.is_usable:
            context.update(name, result.output)
            if self._progress:
                self._progress.finish_stage(name, result.status)
            await self._emit_event(EventType.AGENT_COMPLETED, agent_name=name, data={
                "status": result.status,
                "token_usage": result.token_usage,
                "duration_ms": result.duration_ms,
            })
            logger.info(
                "orchestrator.agent_completed",
                agent=name,
                status=result.status,
                tokens=result.token_usage,
                duration_ms=result.duration_ms,
            )
        else:
            context.update(name, result.output or {})
            report.errors.append(
                f"Agent '{name}' failed: {result.error or 'unknown error'}"
            )
            if self._progress:
                self._progress.finish_stage(name, result.status)
            await self._emit_event(EventType.AGENT_FAILED, agent_name=name, data={
                "status": result.status,
                "error": result.error,
            })
            logger.warning(
                "orchestrator.agent_failed",
                agent=name,
                status=result.status,
                error=result.error,
            )

        return result

    # ------------------------------------------------------------------
    #  Legacy pipeline execution (sequential, for ``run()``)
    # ------------------------------------------------------------------

    async def _execute_pipeline(self, context: AgentContext) -> None:
        """Run the pipeline stages in the legacy sequential order."""

        # Stage 1: Planner
        await self._run_agent(self._planner, context)

        # Stage 2: Static engine
        await self._run_static_engine(context)

        # Stage 3: Coder
        await self._run_agent(self._coder, context)

        # Stage 4: Reviewer <-> Coder loop
        await self._review_loop(context)

        # Stage 5 & 6: Tester + Docs (parallel)
        await self._run_parallel([self._tester, self._docs], context)

    async def _run_agent(
        self, agent: BaseAgent, context: AgentContext,
    ) -> AgentResult:
        """Run a single agent with circuit-breaker protection (legacy)."""
        name = agent.name

        if self._circuit_breaker.is_open(name):
            logger.warning(
                "pipeline.agent_bypassed", agent=name, reason="circuit_breaker",
            )
            fallback = agent.get_fallback(context)
            context.update(name, fallback)
            context.save_checkpoint(name)
            result = AgentResult.from_error(
                error="Circuit breaker open",
                fallback_output=fallback,
            )
            if self._progress:
                self._progress.start_stage(name)
                self._progress.finish_stage(name, "bypassed")
            return result

        if self._progress:
            self._progress.start_stage(name)

        result = await agent.safe_execute(context)

        if result.is_usable:
            self._circuit_breaker.record_success(name)
            context.update(name, result.output)
        else:
            self._circuit_breaker.record_failure(name, result.error or "unknown")
            context.update(name, result.output or {})

        context.save_checkpoint(name)

        if self._progress:
            self._progress.finish_stage(name, result.status)

        return result

    async def _run_parallel(
        self, agents: List[BaseAgent], context: AgentContext,
    ) -> List[AgentResult]:
        """Run multiple agents concurrently (legacy)."""
        tasks = [self._run_agent(agent, context) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final: List[AgentResult] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(
                    "pipeline.parallel_agent.failed",
                    agent=agents[i].name,
                    error=str(r),
                )
                final.append(AgentResult.from_error(str(r)))
            else:
                final.append(r)
        return final

    async def _review_loop(self, context: AgentContext) -> None:
        """Reviewer -> Coder feedback loop (legacy)."""
        for iteration in range(1, self.config.max_review_loops + 1):
            logger.info("pipeline.review_loop", iteration=iteration)

            review_result = await self._run_agent(self._reviewer, context)

            files_needing_regen = review_result.output.get(
                "files_needing_regen", [],
            )
            if not files_needing_regen:
                logger.info(
                    "pipeline.review_loop.done", reason="all_files_acceptable",
                )
                break

            if iteration < self.config.max_review_loops:
                logger.info(
                    "pipeline.review_loop.regen", files=files_needing_regen,
                )
                await self._run_agent(self._coder, context)

    # ------------------------------------------------------------------
    #  Static engine integration
    # ------------------------------------------------------------------

    async def _run_static_engine(self, context: AgentContext) -> None:
        """Integrate with the existing migration pipeline in ``backend.migrator``.

        Runs the static converters (parser, flow_converter, spring_generator)
        and populates the context with generated files and unknown elements
        for the coder agent.
        """
        if self._progress:
            self._progress.start_stage("static_engine")

        await self._emit_event(EventType.STATIC_ENGINE_STARTED)

        trace = context.start_trace("static_engine")
        start = time.monotonic()

        try:
            xml_files = context.get_artifact("xml_files") or {}
            config = context.get_artifact("config") or {}

            from backend.migrator.parser import MuleSoftParser
            from backend.migrator.flow_converter import FlowConverter
            from backend.migrator.connector_mapper import ConnectorMapper
            from backend.migrator.dataweave_converter import DataWeaveConverter
            from backend.migrator.spring_generator import SpringBootGenerator

            generated_files: Dict[str, str] = {}
            unknown_elements: List[dict] = []
            unknown_dataweave: List[dict] = []
            unknown_connectors: List[dict] = []
            unknown_sources: List[dict] = []

            parser = MuleSoftParser()
            mapper = ConnectorMapper()
            dw_converter = DataWeaveConverter()
            all_parsed = {}

            group_id = config.get("group_id", "com.example")
            artifact_id = config.get("artifact_id", "migrated-app")
            java_version = config.get("java_version", "17")

            for filename, xml_content in xml_files.items():
                try:
                    parsed = parser.parse(xml_content)
                    if parsed is None:
                        continue

                    all_parsed = parsed
                    context.set_artifact("parsed_data", parsed)

                    # Convert flows using correct API: FlowConverter(dw_converter, mapper)
                    converter = FlowConverter(dw_converter, mapper)
                    conversion_result = converter.convert(parsed, {})
                    if isinstance(conversion_result, dict):
                        files_dict = conversion_result.get("files", {})
                        if not files_dict:
                            for k, v in conversion_result.items():
                                if isinstance(v, str) and ("." in k or "/" in k):
                                    files_dict[k] = v
                        generated_files.update(files_dict)
                        unknown_elements.extend(conversion_result.get("unknown_elements", []))
                        unknown_dataweave.extend(conversion_result.get("unknown_dataweave", []))
                        unknown_connectors.extend(conversion_result.get("unknown_connectors", []))
                        unknown_sources.extend(conversion_result.get("unknown_sources", []))

                except Exception as exc:
                    logger.warning("static_engine.file_failed", filename=filename, error=str(exc))

            # Generate Spring project skeleton using correct API
            try:
                if all_parsed:
                    generator = SpringBootGenerator(
                        project_name=artifact_id,
                        group_id=group_id,
                        java_version=java_version,
                    )
                    connectors = all_parsed.get("connectors", set())
                    if isinstance(connectors, set):
                        connectors = list(connectors)
                    project_files = generator.generate(
                        generated_files,
                        {"connectors": connectors},
                        all_parsed,
                    )
                    if isinstance(project_files, dict):
                        for k, v in project_files.items():
                            if isinstance(v, str):
                                generated_files[k] = v
            except Exception as exc:
                logger.warning("static_engine.generate_failed", error=str(exc))

            # Store artifacts for downstream agents
            context.set_artifact("generated_files", generated_files)
            context.set_artifact("unknown_elements", unknown_elements)
            context.set_artifact("unknown_dataweave", unknown_dataweave)
            context.set_artifact("unknown_connectors", unknown_connectors)
            context.set_artifact("unknown_sources", unknown_sources)

            duration_ms = int((time.monotonic() - start) * 1000)
            context.finish_trace("static_engine", status="success")
            context.update("static_engine", {
                "files_generated": len(generated_files),
                "unknown_elements": len(unknown_elements),
                "unknown_dataweave": len(unknown_dataweave),
                "unknown_connectors": len(unknown_connectors),
                "unknown_sources": len(unknown_sources),
            })
            context.save_checkpoint("static_engine")

            logger.info(
                "static_engine.complete",
                files=len(generated_files),
                unknowns=(
                    len(unknown_elements) + len(unknown_dataweave)
                    + len(unknown_connectors) + len(unknown_sources)
                ),
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            context.finish_trace("static_engine", status="error", error=str(exc))
            logger.error("static_engine.failed", error=str(exc), exc_info=True)

            # Ensure downstream agents have something to work with
            if context.get_artifact("generated_files") is None:
                context.set_artifact("generated_files", {})
            for key in (
                "unknown_elements", "unknown_dataweave",
                "unknown_connectors", "unknown_sources",
            ):
                if context.get_artifact(key) is None:
                    context.set_artifact(key, [])

        if self._progress:
            self._progress.finish_stage("static_engine", "success")

        await self._emit_event(EventType.STATIC_ENGINE_COMPLETED)

    # ------------------------------------------------------------------
    #  Review feedback loop (new-style, for ``run_pipeline``)
    # ------------------------------------------------------------------

    async def _review_feedback_loop(
        self,
        context: AgentContext,
        report: PipelineReport,
    ) -> None:
        """Re-run coder + reviewer if the reviewer flagged files for regen."""
        reviewer_result = context.get_agent_result("reviewer")
        if not reviewer_result:
            return

        files_needing_regen = reviewer_result.get("files_needing_regen", [])
        if not files_needing_regen:
            return

        await self._emit_event(EventType.REVIEW_LOOP_STARTED, data={
            "files_needing_regen": files_needing_regen,
        })

        for loop_iter in range(1, self.config.max_review_loops + 1):
            logger.info(
                "orchestrator.review_loop",
                iteration=loop_iter,
                files=files_needing_regen,
            )

            # Re-run coder
            if self._coder:
                await self._execute_agent(
                    f"coder_regen_{loop_iter}",
                    self._coder,
                    context,
                    report,
                )

            # Re-run reviewer
            if self._reviewer:
                await self._execute_agent(
                    f"reviewer_recheck_{loop_iter}",
                    self._reviewer,
                    context,
                    report,
                )

            # Check if further regen is needed
            reviewer_state = context.get_agent_result("reviewer") or {}
            files_needing_regen = reviewer_state.get("files_needing_regen", [])
            if not files_needing_regen:
                break

        await self._emit_event(EventType.REVIEW_LOOP_COMPLETED, data={
            "iterations": loop_iter,
        })

    # ------------------------------------------------------------------
    #  DAG helpers
    # ------------------------------------------------------------------

    def _topological_sort(self) -> List[str]:
        """Kahn's algorithm for topological ordering of the DAG.

        Raises ``ValueError`` if the graph contains a cycle.
        """
        in_degree: Dict[str, int] = {}
        for name, node in self._dag.items():
            in_degree.setdefault(name, 0)
            in_degree[name] = sum(1 for d in node.dependencies if d in self._dag)

        queue = sorted(name for name, deg in in_degree.items() if deg == 0)
        result: List[str] = []

        while queue:
            name = queue.pop(0)
            result.append(name)

            for other_name, other_node in self._dag.items():
                if name in other_node.dependencies:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        # Insert sorted for deterministic order
                        queue.append(other_name)
                        queue.sort()

        if len(result) != len(self._dag):
            missing = set(self._dag.keys()) - set(result)
            raise ValueError(f"DAG contains a cycle involving: {missing}")

        return result

    def _compute_dag_levels(
        self, execution_order: List[str],
    ) -> List[List[str]]:
        """Group DAG nodes into levels for parallel execution.

        Nodes at the same level have all dependencies in earlier levels.
        """
        node_level: Dict[str, int] = {}

        for name in execution_order:
            node = self._dag[name]
            if not node.dependencies:
                node_level[name] = 0
            else:
                max_dep_level = max(
                    node_level.get(dep, 0)
                    for dep in node.dependencies
                    if dep in self._dag
                )
                node_level[name] = max_dep_level + 1

        if not node_level:
            return []

        max_level = max(node_level.values())
        levels: List[List[str]] = [[] for _ in range(max_level + 1)]
        for name, level in node_level.items():
            levels[level].append(name)

        return levels

    def _should_run_agent(self, name: str, context: AgentContext) -> bool:
        """Decide whether an agent should run."""
        # Explicitly skipped
        if name in self.config.skip_agents:
            return False

        # Already completed
        trace = context.agent_traces.get(name)
        if trace and trace.status == "success":
            return False

        # Dry-run: only planner and static_engine
        if self.config.dry_run and name not in ("planner", "static_engine"):
            return False

        # Planner may declare some agents unnecessary
        plan = context.get_artifact("migration_plan")
        if plan and name not in ("planner", "static_engine"):
            needed = plan.get("estimated_agents_needed", [])
            if needed and name not in needed and plan.get("use_full_pipeline", True):
                return False

        return True

    # ------------------------------------------------------------------
    #  Checkpoint helpers
    # ------------------------------------------------------------------

    def _save_checkpoint(self, context: AgentContext, agent_name: str) -> None:
        """Save a checkpoint after an agent completes."""
        context.save_checkpoint(agent_name)

        if self.config.checkpoint_dir:
            self._persist_checkpoint_to_disk(context, agent_name)

        logger.debug("orchestrator.checkpoint_saved", agent=agent_name)

    def _persist_checkpoint_to_disk(
        self, context: AgentContext, agent_name: str,
    ) -> None:
        """Write checkpoint JSON to disk for crash recovery."""
        try:
            cp_dir = Path(self.config.checkpoint_dir) / context.id
            cp_dir.mkdir(parents=True, exist_ok=True)

            checkpoint_data = {
                "agent_name": agent_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pipeline_state": context.pipeline_state,
                "token_usage": context.token_usage,
                "total_cost_usd": context.total_cost_usd,
            }

            filepath = cp_dir / f"{agent_name}.json"
            filepath.write_text(
                json.dumps(checkpoint_data, indent=2, default=str),
            )
        except Exception as exc:
            logger.warning(
                "orchestrator.checkpoint_disk_failed",
                agent=agent_name,
                error=str(exc),
            )

    def _find_resume_point(
        self,
        context: AgentContext,
        execution_order: List[str],
    ) -> Optional[str]:
        """Identify the last agent that completed successfully."""
        last_completed: Optional[str] = None
        for agent_name in execution_order:
            trace = context.agent_traces.get(agent_name)
            if trace and trace.status == "success":
                last_completed = agent_name
            else:
                break
        return last_completed

    # ------------------------------------------------------------------
    #  Status determination
    # ------------------------------------------------------------------

    def _determine_final_status(self, report: PipelineReport) -> PipelineStatus:
        """Derive the overall pipeline status from individual agent results."""
        if self.config.dry_run:
            return PipelineStatus.DRY_RUN

        if not report.agents_executed:
            return PipelineStatus.FAILED

        statuses = [
            r.get("status", "error")
            for r in report.agent_results.values()
            if not isinstance(r.get("status"), str) or not r["status"].startswith("_")
        ]

        if all(s == "success" for s in statuses):
            return PipelineStatus.COMPLETED
        if any(s in ("success", "partial") for s in statuses):
            return PipelineStatus.PARTIAL
        return PipelineStatus.FAILED

    # ------------------------------------------------------------------
    #  Memory persistence
    # ------------------------------------------------------------------

    def _persist_to_memory(
        self, context: AgentContext, report: PipelineReport,
    ) -> None:
        """Store the run in agent memory for future recall."""
        if self._memory is None:
            return
        try:
            summary_result = AgentResult(
                status=(
                    "success"
                    if report.status == PipelineStatus.COMPLETED
                    else "partial"
                ),
                output=report.to_dict(),
                token_usage=report.total_tokens,
                duration_ms=report.duration_ms,
            )
            self._memory.store(context, summary_result)
        except Exception as exc:
            logger.warning("orchestrator.memory_persist_failed", error=str(exc))

    # ------------------------------------------------------------------
    #  Event / callback system
    # ------------------------------------------------------------------

    async def _emit_event(
        self,
        event_type: EventType,
        agent_name: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create an event, log it, and dispatch to all registered callbacks.

        Supports both synchronous and asynchronous callbacks.
        """
        event = PipelineEvent(
            event_type=event_type,
            agent_name=agent_name,
            data=data or {},
        )
        self._events.append(event)

        # Legacy dict-style callback
        if self._event_callback:
            try:
                self._event_callback(event.to_dict())
            except Exception as exc:
                logger.warning(
                    "orchestrator.legacy_callback_error",
                    event_type=event_type.value,
                    error=str(exc),
                )

        # New-style PipelineEvent callbacks
        for cb in self._callbacks:
            try:
                ret = cb(event)
                if asyncio.iscoroutine(ret) or asyncio.isfuture(ret):
                    await ret
            except Exception as exc:
                logger.warning(
                    "orchestrator.callback_error",
                    event_type=event_type.value,
                    error=str(exc),
                )
