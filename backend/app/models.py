from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Node(Base):
    __tablename__ = "nodes"

    node_id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auth_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    auth_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_from: Mapped[str] = mapped_column(String, default="bootstrap")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NodeSnapshot(Base):
    __tablename__ = "node_snapshots"

    snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    gpu_json: Mapped[list] = mapped_column(JSON, nullable=False)
    cpu_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    memory_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    ollama_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    health_status: Mapped[str] = mapped_column(String, nullable=False)


class Run(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    detail_type: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    action_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ModelPlacement(Base):
    __tablename__ = "model_placements"

    placement_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model_digest: Mapped[str | None] = mapped_column(String, nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class RoutingRule(Base):
    __tablename__ = "routing_rules"

    rule_id: Mapped[str] = mapped_column(String, primary_key=True)
    priority_class: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingRuleNode(Base):
    __tablename__ = "routing_rule_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))


class WarningRecord(Base):
    __tablename__ = "warning_records"

    warning_id: Mapped[str] = mapped_column(String, primary_key=True)
    warning_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    node_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class EvalSuite(Base):
    __tablename__ = "eval_suites"

    suite_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class EvalCase(Base):
    __tablename__ = "eval_cases"

    case_id: Mapped[str] = mapped_column(String, primary_key=True)
    suite_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class EvalSchedule(Base):
    __tablename__ = "eval_schedules"

    schedule_id: Mapped[str] = mapped_column(String, primary_key=True)
    suite_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_execute: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    next_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_queued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
