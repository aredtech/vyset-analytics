from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class CameraStatus(str, Enum):
    """Camera status enum."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class ROIZone(BaseModel):
    """Region of Interest zone definition."""
    model_config = {"protected_namespaces": ()}
    
    name: str
    points: List[List[float]]  # List of [x, y] coordinates


class CameraParameters(BaseModel):
    """Camera processing parameters."""
    model_config = {"protected_namespaces": ()}
    
    detection_classes: List[str] = Field(default_factory=lambda: ["person", "car", "truck", "garbage"])
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    roi_zones: List[ROIZone] = Field(default_factory=list)
    enable_motion_detection: bool = True
    enable_object_detection: bool = True
    enable_garbage_detection: bool = True
    enable_anpr: bool = False
    motion_threshold: float = Field(default=0.1, ge=0.0, le=1.0)
    frame_skip: int = Field(default=1, ge=1)
    max_fps: int = Field(default=30, ge=1)
    
    # Object tracking parameters
    enable_object_tracking: bool = Field(default=True, description="Enable object tracking (ByteTrack)")
    track_buffer_frames: int = Field(default=30, ge=1, description="Frames to wait before considering object 'left'")
    min_dwell_time_seconds: float = Field(default=1.0, ge=0.0, description="Minimum time before triggering 'left' event")
    tracking_confidence_threshold: float = Field(default=0.3, ge=0.0, le=1.0, description="Confidence threshold for tracking")
    
    # Garbage detection parameters
    garbage_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence threshold for garbage detection")
    enable_garbage_tracking: bool = Field(default=False, description="Enable garbage tracking (ByteTrack)")
    garbage_track_buffer_frames: int = Field(default=30, ge=1, description="Frames to wait before considering garbage object 'left'")
    garbage_min_dwell_time_seconds: float = Field(default=1.0, ge=0.0, description="Minimum time before triggering garbage 'left' event")
    garbage_tracking_confidence_threshold: float = Field(default=0.3, ge=0.0, le=1.0, description="Confidence threshold for garbage tracking")
    
    # Event filtering parameters (for motion and ANPR)
    motion_cooldown_seconds: float = Field(default=2.0, ge=0.0, description="Minimum seconds between motion events")
    anpr_cooldown_seconds: float = Field(default=3.0, ge=0.0, description="Minimum seconds between ANPR events for same plate")
    
    # Event retention parameters
    retention_days: int = Field(default=30, ge=1, le=365, description="Number of days to retain events for this camera (1-365)")


class CameraConfig(BaseModel):
    """Camera configuration model."""
    model_config = {"protected_namespaces": ()}
    
    camera_id: str
    camera_name: Optional[str] = Field(default=None, description="Human-readable camera name")
    status: CameraStatus = CameraStatus.ACTIVE
    stream_url: str
    parameters: CameraParameters = Field(default_factory=CameraParameters)


class BoundingBox(BaseModel):
    """Bounding box coordinates (normalized 0-1)."""
    model_config = {"protected_namespaces": ()}
    
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(ge=0.0, le=1.0)
    height: float = Field(ge=0.0, le=1.0)


class Detection(BaseModel):
    """Single object detection."""
    model_config = {"protected_namespaces": ()}
    
    class_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBox
    track_id: Optional[int] = None  # Unique tracking ID (if tracking enabled)


class ModelInfo(BaseModel):
    """Model information."""
    model_config = {"protected_namespaces": ()}
    
    model_type: str
    version: str


class DetectionEvent(BaseModel):
    """Object detection event."""
    model_config = {"protected_namespaces": ()}
    
    event_type: str = "detection"
    camera_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    detections: List[Detection]
    frame_number: int
    model_info: ModelInfo


class MotionEvent(BaseModel):
    """Motion detection event."""
    model_config = {"protected_namespaces": ()}
    
    event_type: str = "motion"
    camera_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    motion_intensity: float = Field(ge=0.0, le=1.0)
    affected_area_percentage: float = Field(ge=0.0, le=1.0)
    frame_number: int


class ANPRResult(BaseModel):
    """ANPR detection result."""
    model_config = {"protected_namespaces": ()}
    
    license_plate: str
    confidence: float = Field(ge=0.0, le=1.0)
    region: Optional[str] = None


class ANPREvent(BaseModel):
    """ANPR event."""
    model_config = {"protected_namespaces": ()}
    
    event_type: str = "anpr"
    camera_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    anpr_result: ANPRResult
    frame_number: int


class TrackingEvent(BaseModel):
    """Tracking event for object lifecycle (enter/leave/update)."""
    model_config = {"protected_namespaces": ()}
    
    event_type: str = "tracking"
    camera_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    track_id: int
    tracking_action: str  # "entered", "left", "updated"
    class_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBox
    frame_number: int
    dwell_time_seconds: Optional[float] = None  # For "left" events
    model_info: Optional[ModelInfo] = None


class CameraListResponse(BaseModel):
    """Response for listing cameras."""
    model_config = {"protected_namespaces": ()}
    
    cameras: List[CameraConfig]
    count: int


class HealthResponse(BaseModel):
    """Health check response."""
    model_config = {"protected_namespaces": ()}
    
    status: str
    redis_connected: bool
    active_cameras: int

