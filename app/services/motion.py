import cv2
import numpy as np
from typing import Optional
from app.models.event_models import MotionEvent
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MotionDetector:
    """Motion detection service using frame differencing."""
    
    def __init__(self):
        """Initialize motion detector."""
        self.prev_frame = None
        self.motion_mask = None  # Store last motion mask for snapshot
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=16,
            detectShadows=False
        )
    
    def detect(
        self,
        frame: np.ndarray,
        camera_id: str,
        frame_number: int,
        motion_threshold: float = 0.1
    ) -> Optional[MotionEvent]:
        """
        Detect motion in a frame.
        
        Args:
            frame: Input frame (numpy array)
            camera_id: Camera identifier
            frame_number: Frame number
            motion_threshold: Minimum motion intensity threshold (0-1)
            
        Returns:
            MotionEvent if motion detected, None otherwise
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            # Initialize previous frame
            if self.prev_frame is None:
                self.prev_frame = gray
                return None
            
            # Compute absolute difference
            frame_delta = cv2.absdiff(self.prev_frame, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            # Calculate motion metrics
            motion_pixels = cv2.countNonZero(thresh)
            total_pixels = thresh.shape[0] * thresh.shape[1]
            affected_area = motion_pixels / total_pixels
            
            # Calculate motion intensity (normalized)
            motion_intensity = float(np.mean(frame_delta) / 255.0)
            
            # Store motion mask for snapshot
            self.motion_mask = thresh
            
            # Update previous frame
            self.prev_frame = gray
            
            # Return event if motion detected
            if motion_intensity >= motion_threshold or affected_area >= motion_threshold:
                return MotionEvent(
                    camera_id=camera_id,
                    motion_intensity=motion_intensity,
                    affected_area_percentage=affected_area,
                    frame_number=frame_number
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Motion detection error for camera {camera_id}: {e}")
            return None
    
    def reset(self):
        """Reset motion detector state."""
        self.prev_frame = None

