from ultralytics import YOLO
import numpy as np
import torch
from typing import List, Optional, Union
from app.core.config import get_settings
from app.models.event_models import Detection, BoundingBox, DetectionEvent, TrackingEvent, ModelInfo
from app.utils.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)
settings = get_settings()

# Fix for PyTorch 2.6+ weights_only security change
# Monkey patch torch.load to use weights_only=False for trusted ultralytics models
# This is safe because we only load official YOLOv8 models from ultralytics
_original_torch_load = torch.load

def _patched_torch_load(*args, **kwargs):
    """Patched torch.load that sets weights_only=False for compatibility with YOLO models."""
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)

torch.load = _patched_torch_load
logger.debug("Patched torch.load for garbage detection YOLO model compatibility")

# Garbage class names that should be treated as garbage
# These include the original classes and new model classes
GARBAGE_CLASS_NAMES = [
    'garbage', 'trash', 'litter', 'waste',
    'plastic', 'not recyclable', 'food waste'
]

# Normalized class name to use in events (all garbage classes map to "Garbage")
GARBAGE_EVENT_CLASS_NAME = "Garbage"


def is_garbage_class(class_name: str) -> bool:
    """Check if a class name should be treated as garbage."""
    return class_name.lower() in [name.lower() for name in GARBAGE_CLASS_NAMES]


def normalize_garbage_class_name(class_name: str) -> str:
    """Normalize garbage class name to standard "Garbage" for events."""
    if is_garbage_class(class_name):
        return GARBAGE_EVENT_CLASS_NAME
    return class_name


class GarbageDetector:
    """
    Garbage detection service using custom trained YOLO model.
    
    This service uses a specialized model trained specifically for garbage detection.
    It can operate in two modes:
    1. Detection-only mode: Emits DetectionEvent objects
    2. Tracking mode: Uses GarbageTracker for tracking events
    """
    
    def __init__(
        self, 
        model_path: Optional[str] = None,
        enable_tracking: bool = False,
        track_buffer_frames: int = 30,
        min_dwell_time_seconds: float = 1.0,
        tracking_confidence_threshold: float = 0.3
    ):
        """
        Initialize garbage detection model.
        
        Args:
            model_path: Path to garbage detection model file
            enable_tracking: Enable tracking mode (uses GarbageTracker)
            track_buffer_frames: Frames to wait before considering object "left"
            min_dwell_time_seconds: Minimum dwell time to trigger "left" event
            tracking_confidence_threshold: Confidence threshold for tracking
        """
        self.model_path = model_path or settings.garbage_model
        self.model = None
        self.enable_tracking = enable_tracking
        
        # Initialize tracker if tracking is enabled
        self.tracker = None
        if self.enable_tracking:
            try:
                from app.services.garbage_tracker import GarbageTracker
                self.tracker = GarbageTracker(
                    model_path=self.model_path,
                    enable_tracking=True,
                    track_buffer_frames=track_buffer_frames,
                    min_dwell_time_seconds=min_dwell_time_seconds,
                    tracking_confidence_threshold=tracking_confidence_threshold
                )
                logger.info("GarbageDetector initialized with tracking enabled")
            except ImportError as e:
                logger.error(f"Failed to import GarbageTracker: {e}")
                logger.warning("Falling back to detection-only mode")
                self.enable_tracking = False
        else:
            logger.info("GarbageDetector initialized in detection-only mode")
        
        self._load_model()
    
    def _load_model(self):
        """Load garbage detection YOLO model."""
        try:
            logger.info(f"Loading garbage detection YOLO model: {self.model_path}")
            self.model = YOLO(self.model_path)
            
            # Debug model information
            logger.info(f"Model info - task: {getattr(self.model, 'task', 'unknown')}")
            logger.info(f"Model info - names: {getattr(self.model, 'names', 'unknown')}")
            logger.info(f"Model info - model: {type(self.model.model)}")
            
            logger.info("Garbage detection YOLO model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load garbage detection YOLO model: {e}")
            raise
    
    def detect(
        self,
        frame: np.ndarray,
        camera_id: str,
        frame_number: int,
        confidence_threshold: float = 0.5
    ) -> Union[Optional[DetectionEvent], List[TrackingEvent]]:
        """
        Perform garbage detection on frame.
        
        Args:
            frame: Input frame (numpy array)
            camera_id: Camera identifier
            frame_number: Frame number
            confidence_threshold: Minimum confidence threshold
            
        Returns:
            DetectionEvent object if garbage detected (detection mode), 
            List of TrackingEvent objects (tracking mode), 
            None/empty list otherwise
        """
        try:
            # Use tracker if tracking is enabled
            if self.enable_tracking and self.tracker is not None:
                return self.tracker.detect(frame, camera_id, frame_number, confidence_threshold)
            
            # Detection-only mode
            results = self.model(frame, verbose=False)
            
            detections = []
            
            # Process results
            for result in results:
                boxes = result.boxes
                
                if len(boxes) == 0:
                    continue
                
                for i in range(len(boxes)):
                    confidence = float(boxes.conf[i])
                    
                    # Filter by confidence
                    if confidence < confidence_threshold:
                        continue
                    
                    # Get class name
                    class_id = int(boxes.cls[i])
                    class_name = self.model.names[class_id]
                    
                    # Only process garbage detections
                    if not is_garbage_class(class_name):
                        continue
                    
                    # Normalize class name to "Garbage" for events
                    normalized_class_name = normalize_garbage_class_name(class_name)
                    
                    # Get bounding box (xyxy format)
                    box = boxes.xyxy[i].cpu().numpy()
                    
                    # Normalize coordinates
                    h, w = frame.shape[:2]
                    x1, y1, x2, y2 = box
                    
                    bbox = BoundingBox(
                        x=float(x1 / w),
                        y=float(y1 / h),
                        width=float((x2 - x1) / w),
                        height=float((y2 - y1) / h)
                    )
                    
                    # Create detection with normalized class name
                    detection = Detection(
                        class_name=normalized_class_name,
                        confidence=confidence,
                        bounding_box=bbox,
                        track_id=None  # No tracking for detection-only approach
                    )
                    detections.append(detection)
                    
                    logger.info(f"Camera {camera_id}: Garbage {class_name} detected (mapped to {normalized_class_name}, confidence={confidence:.2f})")
            
            # Return DetectionEvent if any garbage was detected
            if detections:
                model_info = ModelInfo(
                    model_type="garbage_detection",
                    version="1.0.0"
                )
                
                event = DetectionEvent(
                    camera_id=camera_id,
                    detections=detections,
                    frame_number=frame_number,
                    model_info=model_info
                )
                return event
            
            return None
            
        except Exception as e:
            logger.error(f"Garbage detection error for camera {camera_id}: {e}", exc_info=True)
            return None if not self.enable_tracking else []
    
    def get_active_tracks_summary(self) -> dict:
        """Get summary of currently tracked garbage objects (tracking mode only)."""
        if self.enable_tracking and self.tracker is not None:
            return self.tracker.get_active_tracks_summary()
        return {}
    
    def reset_tracking(self):
        """Reset all tracking state (tracking mode only)."""
        if self.enable_tracking and self.tracker is not None:
            self.tracker.reset_tracking()
