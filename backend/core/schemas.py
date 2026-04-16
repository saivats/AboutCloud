from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TokenRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    api_key: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class DataPoint(BaseModel):
    model_config = ConfigDict(strict=True)
    timestamp: datetime
    value: float


class MetricIngestRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    tenant_id: str
    cluster_id: str
    node_id: str
    metric_name: str
    datapoints: List[DataPoint] = Field(..., min_length=1)
    metadata: Dict[str, str] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    ingested: int
    failed: int
    validation_errors: List[str] = Field(default_factory=list)


class MetricPoint(BaseModel):
    model_config = ConfigDict(strict=True)
    timestamp: datetime
    value: float


class MetricQueryResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    data: List[MetricPoint]
    total: int
    page: int
    page_size: int
    has_next: bool


class AnomalyInsight(BaseModel):
    model_config = ConfigDict(strict=True)
    summary: str
    baseline_value: Optional[float] = None
    observed_value: Optional[float] = None
    deviation_factor: Optional[float] = None
    pattern_description: Optional[str] = None
    recommendation: Optional[str] = None


class AnomalyResultSchema(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)
    id: Optional[str] = None
    tenant_id: str
    cluster_id: str
    node_id: str
    metric_name: str
    window_start: datetime
    window_end: datetime
    anomaly_score: float
    anomaly_label: str
    confidence: Optional[float] = None
    magnitude: Optional[float] = None
    explanation: Optional[str] = None
    insight: Optional[AnomalyInsight] = None
    detected_at: Optional[datetime] = None


class AnomalyQueryResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    data: List[AnomalyResultSchema]
    total: int
    page: int
    page_size: int
    has_next: bool


class NodeHealthInfo(BaseModel):
    model_config = ConfigDict(strict=True)
    node_id: str
    score: float
    rank: int


class ClusterHealthInfo(BaseModel):
    model_config = ConfigDict(strict=True)
    cluster_id: str
    health_score: float
    top_anomalous_nodes: List[NodeHealthInfo]
    last_updated: Optional[datetime] = None


class ClusterInsight(BaseModel):
    model_config = ConfigDict(strict=True)
    cluster_id: str
    summary: str
    dominant_anomaly_type: Optional[str] = None
    affected_metrics: List[str] = Field(default_factory=list)
    severity: str = "low"


class HealthResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    tenant_id: str
    clusters: List[ClusterHealthInfo]
    insights: List[ClusterInsight] = Field(default_factory=list)


class DetectRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    cluster_id: str
    node_ids: List[str] = Field(default_factory=list)
    metric_names: List[str] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class DetectResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    job_id: str
    status: str = "queued"


class ErrorResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    error: str
    code: str
    details: Optional[Dict[str, Any]] = None
