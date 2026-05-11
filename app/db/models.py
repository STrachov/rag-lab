from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_id() -> str:
    return uuid4().hex


def utc_now() -> datetime:
    return datetime.now(UTC)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    data_assets: Mapped[list["DataAsset"]] = relationship(back_populates="project")
    parameter_sets: Mapped[list["ParameterSet"]] = relationship(back_populates="project")
    ground_truth_sets: Mapped[list["GroundTruthSet"]] = relationship(back_populates="project")
    saved_experiments: Mapped[list["SavedExperiment"]] = relationship(back_populates="project")


class DataAsset(Base):
    __tablename__ = "data_assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("data_assets.id"))
    storage_path: Mapped[str | None] = mapped_column(Text)
    manifest_hash: Mapped[str | None] = mapped_column(String(255))
    preparation_params_json: Mapped[dict | None] = mapped_column(JSON)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped[Project] = relationship(back_populates="data_assets")
    parent: Mapped["DataAsset | None"] = relationship(remote_side=[id])


class ParameterSet(Base):
    __tablename__ = "parameter_sets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    params_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    params_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped[Project] = relationship(back_populates="parameter_sets")


class GroundTruthSet(Base):
    __tablename__ = "ground_truth_sets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_asset_id: Mapped[str | None] = mapped_column(ForeignKey("data_assets.id"))
    storage_path: Mapped[str | None] = mapped_column(Text)
    manifest_hash: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped[Project] = relationship(back_populates="ground_truth_sets")


class SavedExperiment(Base):
    __tablename__ = "saved_experiments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_asset_id: Mapped[str] = mapped_column(ForeignKey("data_assets.id"), nullable=False)
    ground_truth_set_id: Mapped[str | None] = mapped_column(ForeignKey("ground_truth_sets.id"))
    parameter_set_id: Mapped[str | None] = mapped_column(ForeignKey("parameter_sets.id"))
    params_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    params_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    notes: Mapped[str | None] = mapped_column(Text)
    debug_level: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    code_commit: Mapped[str | None] = mapped_column(String(255))
    pipeline_version: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_json: Mapped[dict | None] = mapped_column(JSON)

    project: Mapped[Project] = relationship(back_populates="saved_experiments")
    metrics: Mapped[list["MetricValue"]] = relationship(back_populates="saved_experiment")


class MetricValue(Base):
    __tablename__ = "metric_values"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    saved_experiment_id: Mapped[str] = mapped_column(ForeignKey("saved_experiments.id"), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_scope: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    saved_experiment: Mapped[SavedExperiment] = relationship(back_populates="metrics")


class DerivedCache(Base):
    __tablename__ = "derived_cache"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    data_asset_id: Mapped[str | None] = mapped_column(ForeignKey("data_assets.id"))
    params_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    cache_type: Mapped[str] = mapped_column(String(50), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
