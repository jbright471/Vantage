"""initial schema

Revision ID: 20260509_0001
Revises:
Create Date: 2026-05-09 13:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260509_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nodes",
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("auth_mode", sa.String(), nullable=True),
        sa.Column("auth_config_json", sa.JSON(), nullable=True),
        sa.Column("created_from", sa.String(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("node_id"),
    )
    op.create_table(
        "node_snapshots",
        sa.Column("snapshot_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("gpu_json", sa.JSON(), nullable=False),
        sa.Column("cpu_json", sa.JSON(), nullable=False),
        sa.Column("memory_json", sa.JSON(), nullable=False),
        sa.Column("ollama_json", sa.JSON(), nullable=False),
        sa.Column("health_status", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index(op.f("ix_node_snapshots_node_id"), "node_snapshots", ["node_id"], unique=False)
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("detail_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("action_type", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(op.f("ix_runs_idempotency_key"), "runs", ["idempotency_key"], unique=False)
    op.create_index(op.f("ix_runs_node_id"), "runs", ["node_id"], unique=False)
    op.create_table(
        "model_placements",
        sa.Column("placement_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("model_digest", sa.String(), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("placement_id"),
    )
    op.create_index(op.f("ix_model_placements_model_name"), "model_placements", ["model_name"], unique=False)
    op.create_index(op.f("ix_model_placements_node_id"), "model_placements", ["node_id"], unique=False)
    op.create_table(
        "routing_rules",
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("priority_class", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("allow_degraded", sa.Boolean(), nullable=False),
        sa.Column("allow_stale", sa.Boolean(), nullable=False),
        sa.Column("allow_unreachable", sa.Boolean(), nullable=False),
        sa.Column("minimum_eval_pass_rate", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("rule_id"),
    )
    op.create_table(
        "routing_rule_nodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_routing_rule_nodes_node_id"), "routing_rule_nodes", ["node_id"], unique=False)
    op.create_index(op.f("ix_routing_rule_nodes_rule_id"), "routing_rule_nodes", ["rule_id"], unique=False)
    op.create_table(
        "routing_rule_history",
        sa.Column("history_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("history_id"),
    )
    op.create_index(op.f("ix_routing_rule_history_rule_id"), "routing_rule_history", ["rule_id"], unique=False)
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "warning_records",
        sa.Column("warning_id", sa.String(), nullable=False),
        sa.Column("warning_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("node_id", sa.String(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("warning_id"),
    )
    op.create_index(op.f("ix_warning_records_node_id"), "warning_records", ["node_id"], unique=False)
    op.create_table(
        "eval_suites",
        sa.Column("suite_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("suite_id"),
    )
    op.create_table(
        "eval_cases",
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("suite_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("expected_json", sa.JSON(), nullable=False),
        sa.Column("score_type", sa.String(), nullable=False),
        sa.Column("score_config_json", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("case_id"),
    )
    op.create_index(op.f("ix_eval_cases_suite_id"), "eval_cases", ["suite_id"], unique=False)
    op.create_table(
        "eval_schedules",
        sa.Column("schedule_id", sa.String(), nullable=False),
        sa.Column("suite_id", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("auto_execute", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("last_queued_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("schedule_id"),
    )
    op.create_index(op.f("ix_eval_schedules_model_name"), "eval_schedules", ["model_name"], unique=False)
    op.create_index(op.f("ix_eval_schedules_node_id"), "eval_schedules", ["node_id"], unique=False)
    op.create_index(op.f("ix_eval_schedules_suite_id"), "eval_schedules", ["suite_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_eval_schedules_suite_id"), table_name="eval_schedules")
    op.drop_index(op.f("ix_eval_schedules_node_id"), table_name="eval_schedules")
    op.drop_index(op.f("ix_eval_schedules_model_name"), table_name="eval_schedules")
    op.drop_table("eval_schedules")
    op.drop_index(op.f("ix_eval_cases_suite_id"), table_name="eval_cases")
    op.drop_table("eval_cases")
    op.drop_table("eval_suites")
    op.drop_index(op.f("ix_warning_records_node_id"), table_name="warning_records")
    op.drop_table("warning_records")
    op.drop_table("app_settings")
    op.drop_index(op.f("ix_routing_rule_history_rule_id"), table_name="routing_rule_history")
    op.drop_table("routing_rule_history")
    op.drop_index(op.f("ix_routing_rule_nodes_rule_id"), table_name="routing_rule_nodes")
    op.drop_index(op.f("ix_routing_rule_nodes_node_id"), table_name="routing_rule_nodes")
    op.drop_table("routing_rule_nodes")
    op.drop_table("routing_rules")
    op.drop_index(op.f("ix_model_placements_node_id"), table_name="model_placements")
    op.drop_index(op.f("ix_model_placements_model_name"), table_name="model_placements")
    op.drop_table("model_placements")
    op.drop_index(op.f("ix_runs_node_id"), table_name="runs")
    op.drop_index(op.f("ix_runs_idempotency_key"), table_name="runs")
    op.drop_table("runs")
    op.drop_index(op.f("ix_node_snapshots_node_id"), table_name="node_snapshots")
    op.drop_table("node_snapshots")
    op.drop_table("nodes")
