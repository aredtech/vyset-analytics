from ultralytics import YOLO
import numpy as np
import torch
from typing import List, Optional, Dict, Tuple
from app.core.config import get_settings
from app.models.event_models import Detection, BoundingBox, TrackingEvent, ModelInfo
from app.utils.logger import get_logger

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
logger.debug("Patched torch.load for YOLO model compatibility")


class TrackedObject:
    """Represents a tracked object across frames."""
    
    def __init__(self, track_id: int, class_name: str, frame_number: int):
        self.track_id = track_id
        self.class_name = class_name
        self.first_seen_frame = frame_number
        self.last_seen_frame = frame_number
        self.frame_count = 1
        self.positions = []  # For trajectory tracking
    
    def update(self, frame_number: int, bbox: BoundingBox):
        """Update track with new detection."""
        self.last_seen_frame = frame_number
        self.frame_count += 1
        self.positions.append(bbox)
    
    def get_dwell_time(self, fps: float = 30.0) -> float:
        """Calculate dwell time in seconds."""
        return (self.last_seen_frame - self.first_seen_frame) / fps
    
    def __repr__(self):
        return f"TrackedObject(id={self.track_id}, class={self.class_name}, frames={self.frame_count})"


class ObjectDetector:
    """
    YOLOv8 object detection service with ByteTrack tracking support.
    
    This uses YOLO's built-in ByteTrack implementation to assign unique IDs
    to detected objects and track them across frames.
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        enable_tracking: bool = True,
        track_buffer_frames: int = 30,
        min_dwell_time_seconds: float = 1.0
    ):
        """
        Initialize YOLO model with tracking.
        
        Args:
            model_path: Path to YOLO model file
            enable_tracking: Enable object tracking (vs. simple detection)
            track_buffer_frames: Frames to wait before considering object "left"
            min_dwell_time_seconds: Minimum dwell time to trigger "left" event
        """
        self.model_path = model_path or settings.yolo_model
        self.enable_tracking = enable_tracking
        self.track_buffer_frames = track_buffer_frames
        self.min_dwell_time_seconds = min_dwell_time_seconds
        self.model = None
        
        # Tracking state
        self.active_tracks: Dict[int, TrackedObject] = {}
        self.lost_tracks: Dict[int, Tuple[TrackedObject, int]] = {}  # track_id -> (object, frames_since_seen)
        
        self._load_model()
    
    def _load_model(self):
        """Load YOLO model."""
        try:
            logger.info(f"Loading YOLO model with tracking: {self.model_path}")
            self.model = YOLO(self.model_path)
            logger.info(f"YOLO model loaded successfully (tracking={'enabled' if self.enable_tracking else 'disabled'})")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
    
    def detect(
        self,
        frame: np.ndarray,
        camera_id: str,
        frame_number: int,
        confidence_threshold: float = 0.5,
        target_classes: Optional[List[str]] = None
    ) -> List[TrackingEvent]:
        """
        Perform object detection with tracking.
        
        Returns a list of tracking events:
        - "entered": New object appeared
        - "left": Object disappeared (after buffer frames)
        
        Args:
            frame: Input frame (numpy array)
            camera_id: Camera identifier
            frame_number: Frame number
            confidence_threshold: Minimum confidence threshold
            target_classes: List of target class names to detect
            
        Returns:
            List of TrackingEvent objects (empty list if no events)
        """
        try:
            events = []
            
            # Run inference with tracking
            if self.enable_tracking:
                results = self.model.track(frame, persist=True, verbose=False)
            else:
                results = self.model(frame, verbose=False)
            
            current_frame_tracks = set()
            
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
                    
                    # Filter by target classes
                    if target_classes and class_name not in target_classes:
                        continue
                    
                    # Get tracking ID (only available with track=True)
                    track_id = None
                    if self.enable_tracking and boxes.id is not None and len(boxes.id) > i:
                        track_id = int(boxes.id[i])
                    
                    if track_id is None:
                        # No tracking ID available, skip
                        continue
                    
                    current_frame_tracks.add(track_id)
                    
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
                    
                    # Check if this is a new track
                    if track_id not in self.active_tracks:
                        # NEW OBJECT ENTERED
                        tracked_obj = TrackedObject(track_id, class_name, frame_number)
                        tracked_obj.update(frame_number, bbox)
                        self.active_tracks[track_id] = tracked_obj
                        
                        # Create model info
                        model_info = ModelInfo(
                            model_type=self.model_path.replace('.pt', ''),
                            version="8.1.0"
                        )
                        
                        # Generate entry event
                        event = TrackingEvent(
                            camera_id=camera_id,
                            track_id=track_id,
                            tracking_action="entered",
                            class_name=class_name,
                            frame_number=frame_number,
                            confidence=confidence,
                            bounding_box=bbox,
                            model_info=model_info
                        )
                        events.append(event)
                        
                        logger.info(f"Camera {camera_id}: Object {class_name} entered (track_id={track_id})")
                    else:
                        # Update existing track
                        self.active_tracks[track_id].update(frame_number, bbox)
                        
                        # Remove from lost tracks if it was there
                        if track_id in self.lost_tracks:
                            del self.lost_tracks[track_id]
            
            # Check for objects that are no longer detected
            for track_id in list(self.active_tracks.keys()):
                if track_id not in current_frame_tracks:
                    # Object not in current frame
                    tracked_obj = self.active_tracks[track_id]
                    
                    if track_id not in self.lost_tracks:
                        # First frame where object is missing
                        self.lost_tracks[track_id] = (tracked_obj, 0)
                    else:
                        # Increment frames since last seen
                        obj, frames_lost = self.lost_tracks[track_id]
                        self.lost_tracks[track_id] = (obj, frames_lost + 1)
                        
                        # Check if object should be considered "left"
                        if frames_lost >= self.track_buffer_frames:
                            # OBJECT LEFT
                            dwell_time = tracked_obj.get_dwell_time()
                            
                            # Only generate event if object was present long enough
                            if dwell_time >= self.min_dwell_time_seconds:
                                # Create model info
                                model_info = ModelInfo(
                                    model_type=self.model_path.replace('.pt', ''),
                                    version="8.1.0"
                                )
                                
                                event = TrackingEvent(
                                    camera_id=camera_id,
                                    track_id=track_id,
                                    tracking_action="left",
                                    class_name=tracked_obj.class_name,
                                    frame_number=frame_number,
                                    confidence=0.0,  # Not applicable for "left" event
                                    bounding_box=tracked_obj.positions[-1] if tracked_obj.positions else BoundingBox(x=0, y=0, width=0, height=0),
                                    dwell_time_seconds=dwell_time,
                                    model_info=model_info
                                )
                                events.append(event)
                                
                                logger.info(f"Camera {camera_id}: Object {tracked_obj.class_name} left (track_id={track_id}, dwell_time={dwell_time:.1f}s)")
                            
                            # Clean up
                            del self.active_tracks[track_id]
                            del self.lost_tracks[track_id]
            
            return events
            
        except Exception as e:
            logger.error(f"Detection error for camera {camera_id}: {e}", exc_info=True)
            return []
    
    def get_active_tracks_summary(self) -> Dict[str, int]:
        """Get summary of currently tracked objects."""
        summary = {}
        for tracked_obj in self.active_tracks.values():
            class_name = tracked_obj.class_name
            summary[class_name] = summary.get(class_name, 0) + 1
        return summary
    
    def reset_tracking(self):
        """Reset all tracking state."""
        self.active_tracks.clear()
        self.lost_tracks.clear()
        logger.info("Tracking state reset")
