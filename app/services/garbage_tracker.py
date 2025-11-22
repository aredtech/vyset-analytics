from ultralytics import YOLO
import numpy as np
import torch
from typing import List, Optional, Dict, Tuple
import supervision as sv
from app.core.config import get_settings
from app.models.event_models import Detection, BoundingBox, TrackingEvent, ModelInfo
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
logger.debug("Patched torch.load for garbage tracking YOLO model compatibility")


class TrackedGarbage:
    """Represents a tracked garbage object across frames."""
    
    def __init__(self, track_id: int, class_name: str, frame_number: int):
        self.track_id = track_id
        self.class_name = class_name
        self.first_seen_frame = frame_number
        self.last_seen_frame = frame_number
        self.frame_count = 1
        self.positions = []  # For trajectory tracking
        self.confidences = []  # Track confidence over time
    
    def update(self, frame_number: int, bbox: BoundingBox, confidence: float):
        """Update track with new detection."""
        self.last_seen_frame = frame_number
        self.frame_count += 1
        self.positions.append(bbox)
        self.confidences.append(confidence)
    
    def get_dwell_time(self, fps: float = 30.0) -> float:
        """Calculate dwell time in seconds."""
        return (self.last_seen_frame - self.first_seen_frame) / fps
    
    def get_average_confidence(self) -> float:
        """Get average confidence across all detections."""
        return sum(self.confidences) / len(self.confidences) if self.confidences else 0.0
    
    def __repr__(self):
        return f"TrackedGarbage(id={self.track_id}, class={self.class_name}, frames={self.frame_count})"


class GarbageTracker:
    """
    Garbage detection service with ByteTrack tracking support using supervision library.
    
    This service uses a custom trained YOLO model for garbage detection and adds
    tracking capabilities using the supervision library's ByteTrack implementation.
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        enable_tracking: bool = True,
        track_buffer_frames: int = 30,
        min_dwell_time_seconds: float = 1.0,
        tracking_confidence_threshold: float = 0.3
    ):
        """
        Initialize garbage detection model with tracking.
        
        Args:
            model_path: Path to garbage detection YOLO model file
            enable_tracking: Enable object tracking (vs. simple detection)
            track_buffer_frames: Frames to wait before considering object "left"
            min_dwell_time_seconds: Minimum dwell time to trigger "left" event
            tracking_confidence_threshold: Confidence threshold for tracking
        """
        self.model_path = model_path or settings.garbage_model
        self.enable_tracking = enable_tracking
        self.track_buffer_frames = track_buffer_frames
        self.min_dwell_time_seconds = min_dwell_time_seconds
        self.tracking_confidence_threshold = tracking_confidence_threshold
        self.model = None
        
        # Tracking state
        self.active_tracks: Dict[int, TrackedGarbage] = {}
        self.lost_tracks: Dict[int, Tuple[TrackedGarbage, int]] = {}  # track_id -> (object, frames_since_seen)
        
        # Initialize ByteTrack tracker from supervision
        if self.enable_tracking:
            self.tracker = sv.ByteTrack()
            logger.info("Initialized ByteTrack tracker for garbage detection")
        else:
            self.tracker = None
        
        self._load_model()
    
    def _load_model(self):
        """Load garbage detection YOLO model."""
        try:
            logger.info(f"Loading garbage detection YOLO model with tracking: {self.model_path}")
            self.model = YOLO(self.model_path)
            
            # Debug model information
            logger.info(f"Model info - task: {getattr(self.model, 'task', 'unknown')}")
            logger.info(f"Model info - names: {getattr(self.model, 'names', 'unknown')}")
            logger.info(f"Model info - model: {type(self.model.model)}")
            
            logger.info(f"Garbage detection YOLO model loaded successfully (tracking={'enabled' if self.enable_tracking else 'disabled'})")
        except Exception as e:
            logger.error(f"Failed to load garbage detection YOLO model: {e}")
            raise
    
    def detect(
        self,
        frame: np.ndarray,
        camera_id: str,
        frame_number: int,
        confidence_threshold: float = 0.5
    ) -> List[TrackingEvent]:
        """
        Perform garbage detection with tracking.
        
        Returns a list of tracking events:
        - "entered": New garbage object appeared
        - "left": Garbage object disappeared (after buffer frames)
        
        Args:
            frame: Input frame (numpy array)
            camera_id: Camera identifier
            frame_number: Frame number
            confidence_threshold: Minimum confidence threshold for detection
            
        Returns:
            List of TrackingEvent objects (empty list if no events)
        """
        try:
            events = []
            
            # Run inference (detection only)
            results = self.model(frame, verbose=False)
            
            # Convert YOLO results to supervision format
            detections = sv.Detections.from_ultralytics(results[0])
            
            # Filter by confidence threshold
            detections = detections[detections.confidence >= confidence_threshold]
            
            # Filter for garbage classes only
            garbage_class_names = ['garbage', 'trash', 'litter', 'waste']
            garbage_class_ids = []
            for class_id, class_name in self.model.names.items():
                if class_name.lower() in garbage_class_names:
                    garbage_class_ids.append(class_id)
            
            if garbage_class_ids:
                # Filter detections to only include garbage classes
                garbage_mask = np.isin(detections.class_id, garbage_class_ids)
                detections = detections[garbage_mask]
            
            # Apply tracking if enabled
            if self.enable_tracking and self.tracker is not None and len(detections) > 0:
                # Update tracker with new detections
                detections = self.tracker.update_with_detections(detections)
            
            current_frame_tracks = set()
            
            # Process tracked detections
            for i in range(len(detections)):
                confidence = float(detections.confidence[i])
                class_id = int(detections.class_id[i])
                class_name = self.model.names[class_id]
                
                # Get tracking ID (only available with tracking enabled)
                track_id = None
                if self.enable_tracking and detections.tracker_id is not None and len(detections.tracker_id) > i:
                    track_id = int(detections.tracker_id[i])
                
                if track_id is None:
                    # No tracking ID available, skip
                    continue
                
                current_frame_tracks.add(track_id)
                
                # Get bounding box (xyxy format)
                box = detections.xyxy[i]
                
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
                    # NEW GARBAGE OBJECT ENTERED
                    tracked_obj = TrackedGarbage(track_id, class_name, frame_number)
                    tracked_obj.update(frame_number, bbox, confidence)
                    self.active_tracks[track_id] = tracked_obj
                    
                    # Create model info
                    model_info = ModelInfo(
                        model_type="garbage_detection",
                        version="1.0.0"
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
                    
                    logger.info(f"Camera {camera_id}: Garbage {class_name} entered (track_id={track_id})")
                else:
                    # Update existing track
                    self.active_tracks[track_id].update(frame_number, bbox, confidence)
                    
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
                            # GARBAGE OBJECT LEFT
                            dwell_time = tracked_obj.get_dwell_time()
                            
                            # Only generate event if object was present long enough
                            if dwell_time >= self.min_dwell_time_seconds:
                                # Create model info
                                model_info = ModelInfo(
                                    model_type="garbage_detection",
                                    version="1.0.0"
                                )
                                
                                # Use average confidence for "left" event
                                avg_confidence = tracked_obj.get_average_confidence()
                                
                                event = TrackingEvent(
                                    camera_id=camera_id,
                                    track_id=track_id,
                                    tracking_action="left",
                                    class_name=tracked_obj.class_name,
                                    frame_number=frame_number,
                                    confidence=avg_confidence,
                                    bounding_box=tracked_obj.positions[-1] if tracked_obj.positions else BoundingBox(x=0, y=0, width=0, height=0),
                                    dwell_time_seconds=dwell_time,
                                    model_info=model_info
                                )
                                events.append(event)
                                
                                logger.info(f"Camera {camera_id}: Garbage {tracked_obj.class_name} left (track_id={track_id}, dwell_time={dwell_time:.1f}s)")
                            
                            # Clean up
                            del self.active_tracks[track_id]
                            del self.lost_tracks[track_id]
            
            return events
            
        except Exception as e:
            logger.error(f"Garbage tracking error for camera {camera_id}: {e}", exc_info=True)
            return []
    
    def get_active_tracks_summary(self) -> Dict[str, int]:
        """Get summary of currently tracked garbage objects."""
        summary = {}
        for tracked_obj in self.active_tracks.values():
            class_name = tracked_obj.class_name
            summary[class_name] = summary.get(class_name, 0) + 1
        return summary
    
    def reset_tracking(self):
        """Reset all tracking state."""
        self.active_tracks.clear()
        self.lost_tracks.clear()
        if self.tracker is not None:
            self.tracker.reset()
        logger.info("Garbage tracking state reset")
