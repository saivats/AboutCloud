import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, DateTime, Boolean, ForeignKey, Text, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, DOUBLE_PRECISION
from sqlalchemy.orm import relationship

from backend.core.database import Base


def generate_uuid():
    return uuid.uuid4()


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, unique=True)
    api_key_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    settings = Column(JSONB, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    clusters = relationship("Cluster", back_populates="tenant", cascade="all, delete-orphan")


class Cluster(Base):
    __tablename__ = "clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    region = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="clusters")
    nodes = relationship("Node", back_populates="cluster", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_clusters_tenant_id", "tenant_id"),
    )


class Node(Base):
    __tablename__ = "nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    hostname = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    cluster = relationship("Cluster", back_populates="nodes")

    __table_args__ = (
        Index("ix_nodes_cluster_id", "cluster_id"),
        Index("ix_nodes_tenant_id", "tenant_id"),
    )


class MetricHot(Base):
    __tablename__ = "metrics_hot"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    cluster_id = Column(UUID(as_uuid=True), nullable=False)
    node_id = Column(UUID(as_uuid=True), nullable=False)
    metric_name = Column(String(100), nullable=False, primary_key=True)
    value = Column(DOUBLE_PRECISION, nullable=False)
    extra_metadata = Column("metadata", JSONB, default=dict)

    __table_args__ = (
        Index("ix_metrics_hot_tenant_time", "tenant_id", "time"),
        Index("ix_metrics_hot_lookup", "tenant_id", "cluster_id", "node_id", "metric_name", "time"),
    )


class AnomalyResultRecord(Base):
    __tablename__ = "anomaly_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    cluster_id = Column(UUID(as_uuid=True), nullable=False)
    node_id = Column(UUID(as_uuid=True), nullable=False)
    metric_name = Column(String(100), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    anomaly_score = Column(Float, nullable=False)
    anomaly_label = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=True)
    magnitude = Column(Float, nullable=True)
    explanation = Column(Text, nullable=True)
    detected_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_anomaly_tenant_time", "tenant_id", "detected_at"),
        Index("ix_anomaly_lookup", "tenant_id", "cluster_id", "node_id", "metric_name"),
    )


class AggregatedScoreRecord(Base):
    __tablename__ = "aggregated_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    cluster_id = Column(UUID(as_uuid=True), nullable=True)
    node_id = Column(UUID(as_uuid=True), nullable=True)
    aggregate_score = Column(Float, nullable=False)
    aggregation_strategy = Column(String(20), nullable=False)
    num_metrics_analyzed = Column(Float, nullable=False, default=0)
    num_anomalies_detected = Column(Float, nullable=False, default=0)
    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_agg_tenant_cluster", "tenant_id", "cluster_id"),
        Index("ix_agg_computed", "tenant_id", "computed_at"),
    )
