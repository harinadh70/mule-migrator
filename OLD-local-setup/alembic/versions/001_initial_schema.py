"""Initial schema: users, migration_jobs, build_jobs, agent_traces

Revision ID: 001
Revises:
Create Date: 2026-03-21
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("tenant_id", sa.String(255), nullable=True),
        sa.Column("github_id", sa.String(100), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])
    op.create_index("uq_users_github_id", "users", ["github_id"], unique=True)

    # ── migration_jobs ────────────────────────────────────────
    op.create_table(
        "migration_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("project_name", sa.String(255), nullable=False),
        sa.Column("group_id", sa.String(255), nullable=False),
        sa.Column("java_version", sa.String(10), nullable=False, server_default="17"),
        sa.Column("input_xml_files", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("dataweave_scripts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("llm_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_files", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("llm_validation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("agent_trace", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total_tokens_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_cost_usd", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_migration_jobs_user_id_users"),
            nullable=True,
        ),
        sa.Column("tenant_id", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_migration_jobs"),
    )
    op.create_index("ix_migration_jobs_status", "migration_jobs", ["status"])
    op.create_index("ix_migration_jobs_created_at", "migration_jobs", ["created_at"])
    op.create_index("ix_migration_jobs_user_id", "migration_jobs", ["user_id"])
    op.create_index("ix_migration_jobs_tenant_id", "migration_jobs", ["tenant_id"])
    op.create_index("ix_migration_jobs_tenant_status", "migration_jobs", ["tenant_id", "status"])
    op.create_index("ix_migration_jobs_deleted_at", "migration_jobs", ["deleted_at"])

    # ── build_jobs ────────────────────────────────────────────
    op.create_table(
        "build_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "migration_id",
            sa.String(36),
            sa.ForeignKey("migration_jobs.id", ondelete="CASCADE", name="fk_build_jobs_migration_id_migration_jobs"),
            nullable=False,
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("build_tool", sa.String(50), nullable=False, server_default="maven"),
        sa.Column("build_log", sa.Text(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_build_jobs"),
    )
    op.create_index("ix_build_jobs_migration_id", "build_jobs", ["migration_id"])

    # ── agent_traces ──────────────────────────────────────────
    op.create_table(
        "agent_traces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "migration_id",
            sa.String(36),
            sa.ForeignKey("migration_jobs.id", ondelete="CASCADE", name="fk_agent_traces_migration_id_migration_jobs"),
            nullable=False,
        ),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rag_queries", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rag_results_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("output_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_agent_traces"),
    )
    op.create_index("ix_agent_traces_migration_id", "agent_traces", ["migration_id"])
    op.create_index("ix_agent_traces_agent_name", "agent_traces", ["agent_name"])


def downgrade() -> None:
    op.drop_table("agent_traces")
    op.drop_table("build_jobs")
    op.drop_table("migration_jobs")
    op.drop_table("users")
