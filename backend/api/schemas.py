"""
API Request/Response Schemas

Pydantic models for clear, validated JSON payloads.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ---- Request Models ----

class MetricPointPayload(BaseModel):
    """A single metric data point."""
    timestamp: datetime
    value: float


class MetricIngestRequest(BaseModel):
    """POST /metrics request body."""
    tenant_id: str = Field(..., description="Tenant identifier")
    cluster_id: str = Field(..., description="Cluster identifier")
    node_id: str = Field(..., description="Node identifier")
    metric_name: str = Field(..., description="Metric name (e.g., cpu_usage)")
    data_points: List[MetricPointPayload] = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetricQueryParams(BaseModel):
    """GET /metrics query parameters."""
    tenant_id: str
    cluster_id: str
    node_id: str
    metric_name: str
    start_time: datetime
    end_time: datetime


class AnomalyQueryParams(BaseModel):
    """GET /anomalies query parameters."""
    tenant_id: str
    cluster_id: Optional[str] = None
    start_time: datetime
    end_time: datetime
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


# ---- Response Models ----

class MetricSeriesResponse(BaseModel):
    """Response for metric queries."""
    tenant_id: str
    cluster_id: str
    node_id: str
    metric_name: str
    num_points: int
    timestamps: List[datetime]
    values: List[float]


class AnomalyResultResponse(BaseModel):
    """Single anomaly result in response."""
    tenant_id: str
    cluster_id: str
    node_id: str
    metric_name: str
    anomaly_score: float
    anomaly_label: str
    window_start: datetime
    window_end: datetime
    explanation: Optional[str] = None


class AnomalyQueryResponse(BaseModel):
    """Response for anomaly queries."""
    total: int
    results: List[AnomalyResultResponse]


class HealthNodeScore(BaseModel):
    """Node-level health score."""
    node_id: str
    score: float
    num_anomalies: int


class HealthClusterScore(BaseModel):
    """Cluster-level health score."""
    cluster_id: str
    score: float
    num_nodes: int
    node_scores: List[HealthNodeScore]


class HealthResponse(BaseModel):
    """Response for health endpoint."""
    tenant_id: str
    overall_score: float
    clusters: List[HealthClusterScore]
    timestamp: datetime


class IngestResponse(BaseModel):
    """Response for ingest endpoint."""
    status: str
    tenant_id: str
    metric_name: str
    points_stored: int
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    status_code: int
