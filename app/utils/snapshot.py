"""
Snapshot utility for saving frames with bounding boxes.
"""
import cv2
import os
import numpy as np
from datetime import datetime
from typing import Optional, List
from pathlib import Path
from app.models.event_models import Detection, BoundingBox, ANPRResult
from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class SnapshotManager:
    """Manager for saving event snapshots."""
    
    def __init__(self):
        """Initialize snapshot manager."""
        self.snapshots_dir = Path(settings.snapshots_dir)
        self._ensure_directory_exists()
    
    def _ensure_directory_exists(self):
        """Ensure snapshots directory exists."""
        try:
            self.snapshots_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Snapshots directory initialized: {self.snapshots_dir}")
        except Exception as e:
            logger.error(f"Failed to create snapshots directory: {e}", exc_info=True)
            raise
    
    def _get_snapshot_path(self, camera_id: str, event_type: str, timestamp: datetime) -> str:
        """
        Generate snapshot file path.
        
        Args:
            camera_id: Camera identifier
            event_type: Type of event (detection, motion, anpr, tracking)
            timestamp: Event timestamp
            
        Returns:
            Relative path to snapshot file
        """
        # Create camera subdirectory
        camera_dir = self.snapshots_dir / camera_id
        camera_dir.mkdir(exist_ok=True)
        
        # Create date subdirectory (YYYY-MM-DD)
        date_dir = camera_dir / timestamp.strftime("%Y-%m-%d")
        date_dir.mkdir(exist_ok=True)
        
        # Generate filename: eventtype_HHMMSS_microseconds.png
        # Generate filename: eventtype_HHMMSS_microseconds.ext
        ext = settings.snapshot_format.lower().replace("jpeg", "jpg")
        if not ext:
            ext = "jpg"
            
        filename = f"{event_type}_{timestamp.strftime('%H%M%S')}_{timestamp.microsecond:06d}.{ext}"
        full_path = date_dir / filename
        
        # Return relative path from snapshots_dir
        return str(full_path.relative_to(self.snapshots_dir))
    
    def _denormalize_bbox(self, bbox: BoundingBox, frame_height: int, frame_width: int) -> tuple:
        """
        Convert normalized bounding box to pixel coordinates.
        
        Args:
            bbox: Normalized bounding box (0-1)
            frame_height: Frame height in pixels
            frame_width: Frame width in pixels
            
        Returns:
            Tuple of (x1, y1, x2, y2) in pixels
        """
        x1 = int(bbox.x * frame_width)
        y1 = int(bbox.y * frame_height)
        x2 = int((bbox.x + bbox.width) * frame_width)
        y2 = int((bbox.y + bbox.height) * frame_height)
        return x1, y1, x2, y2
    
    def save_detection_snapshot(
        self,
        frame: np.ndarray,
        camera_id: str,
        detections: List[Detection],
        timestamp: datetime
    ) -> Optional[str]:
        """
        Save snapshot for detection/tracking event with bounding boxes.
        
        Args:
            frame: Video frame
            camera_id: Camera identifier
            detections: List of detections
            timestamp: Event timestamp
            
        Returns:
            Relative path to saved snapshot, or None if failed
        """
        try:
            if not settings.enable_snapshots:
                return None
            
            # Clone frame to avoid modifying original
            annotated_frame = frame.copy()
            height, width = annotated_frame.shape[:2]
            
            # Draw bounding boxes and labels
            for detection in detections:
                x1, y1, x2, y2 = self._denormalize_bbox(detection.bounding_box, height, width)
                
                # Choose color based on class (simple hash-based color)
                color_hash = hash(detection.class_name) % 256
                color = (
                    (color_hash * 50) % 255,
                    (color_hash * 100) % 255,
                    (color_hash * 150) % 255
                )
                
                # Draw rectangle
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                
                # Prepare label
                label = f"{detection.class_name}: {detection.confidence:.2f}"
                if detection.track_id is not None:
                    label += f" (ID:{detection.track_id})"
                
                # Draw label background
                (label_width, label_height), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                )
                cv2.rectangle(
                    annotated_frame,
                    (x1, y1 - label_height - baseline - 5),
                    (x1 + label_width, y1),
                    color,
                    -1
                )
                
                # Draw label text
                cv2.putText(
                    annotated_frame,
                    label,
                    (x1, y1 - baseline - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1
                )
            
            # Generate path and save
            relative_path = self._get_snapshot_path(camera_id, "detection", timestamp)
            full_path = self.snapshots_dir / relative_path
            
            # Set compression parameters
            encode_params = []
            if settings.snapshot_format.lower() in ["jpg", "jpeg"]:
                encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), settings.snapshot_quality]
            elif settings.snapshot_format.lower() == "png":
                # For PNG, quality is compression level (0-9). We'll map the 0-100 scale roughly to 0-9
                compression = int((100 - settings.snapshot_quality) / 10)
                compression = max(0, min(9, compression))
                encode_params = [int(cv2.IMWRITE_PNG_COMPRESSION), compression]

            cv2.imwrite(str(full_path), annotated_frame, encode_params)
            
            logger.debug(f"Saved detection snapshot: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to save detection snapshot: {e}", exc_info=True)
            return None
    
    def save_motion_snapshot(
        self,
        frame: np.ndarray,
        camera_id: str,
        timestamp: datetime,
        motion_mask: Optional[np.ndarray] = None
    ) -> Optional[str]:
        """
        Save snapshot for motion event with optional motion mask overlay.
        
        Args:
            frame: Video frame
            camera_id: Camera identifier
            timestamp: Event timestamp
            motion_mask: Optional motion mask to overlay
            
        Returns:
            Relative path to saved snapshot, or None if failed
        """
        try:
            if not settings.enable_snapshots:
                return None
            
            annotated_frame = frame.copy()
            
            # Overlay motion mask if provided
            if motion_mask is not None:
                # Create red overlay for motion areas
                motion_overlay = np.zeros_like(annotated_frame)
                motion_overlay[:, :, 2] = motion_mask  # Red channel
                
                # Blend with original frame
                annotated_frame = cv2.addWeighted(annotated_frame, 0.7, motion_overlay, 0.3, 0)
            
            # Add timestamp text
            timestamp_text = f"Motion: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            cv2.putText(
                annotated_frame,
                timestamp_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )
            
            # Generate path and save
            relative_path = self._get_snapshot_path(camera_id, "motion", timestamp)
            full_path = self.snapshots_dir / relative_path
            
            # Set compression parameters
            encode_params = []
            if settings.snapshot_format.lower() in ["jpg", "jpeg"]:
                encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), settings.snapshot_quality]
            elif settings.snapshot_format.lower() == "png":
                # For PNG, quality is compression level (0-9). We'll map the 0-100 scale roughly to 0-9
                compression = int((100 - settings.snapshot_quality) / 10)
                compression = max(0, min(9, compression))
                encode_params = [int(cv2.IMWRITE_PNG_COMPRESSION), compression]

            cv2.imwrite(str(full_path), annotated_frame, encode_params)
            
            logger.debug(f"Saved motion snapshot: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to save motion snapshot: {e}", exc_info=True)
            return None
    
    def save_anpr_snapshot(
        self,
        frame: np.ndarray,
        camera_id: str,
        anpr_result: ANPRResult,
        timestamp: datetime,
        bounding_box: Optional[BoundingBox] = None
    ) -> Optional[str]:
        """
        Save snapshot for ANPR event with license plate highlighted.
        
        Args:
            frame: Video frame
            camera_id: Camera identifier
            anpr_result: ANPR detection result
            timestamp: Event timestamp
            bounding_box: Optional bounding box of license plate
            
        Returns:
            Relative path to saved snapshot, or None if failed
        """
        try:
            if not settings.enable_snapshots:
                return None
            
            annotated_frame = frame.copy()
            height, width = annotated_frame.shape[:2]
            
            # Draw bounding box if provided
            if bounding_box:
                x1, y1, x2, y2 = self._denormalize_bbox(bounding_box, height, width)
                
                # Draw green rectangle for license plate
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            
            # Add license plate text at the top
            plate_text = f"Plate: {anpr_result.license_plate} ({anpr_result.confidence:.2f})"
            cv2.rectangle(annotated_frame, (10, 10), (10 + len(plate_text) * 12, 50), (0, 255, 0), -1)
            cv2.putText(
                annotated_frame,
                plate_text,
                (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 0),
                2
            )
            
            # Generate path and save
            relative_path = self._get_snapshot_path(camera_id, "anpr", timestamp)
            full_path = self.snapshots_dir / relative_path
            
            # Set compression parameters
            encode_params = []
            if settings.snapshot_format.lower() in ["jpg", "jpeg"]:
                encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), settings.snapshot_quality]
            elif settings.snapshot_format.lower() == "png":
                # For PNG, quality is compression level (0-9). We'll map the 0-100 scale roughly to 0-9
                compression = int((100 - settings.snapshot_quality) / 10)
                compression = max(0, min(9, compression))
                encode_params = [int(cv2.IMWRITE_PNG_COMPRESSION), compression]

            cv2.imwrite(str(full_path), annotated_frame, encode_params)
            
            logger.debug(f"Saved ANPR snapshot: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to save ANPR snapshot: {e}", exc_info=True)
            return None
    
    def get_snapshot_full_path(self, relative_path: str) -> Path:
        """
        Get full path to snapshot file.
        
        Args:
            relative_path: Relative path from snapshots directory
            
        Returns:
            Full path to snapshot file
        """
        return self.snapshots_dir / relative_path
    
    def delete_snapshot(self, relative_path: str) -> bool:
        """
        Delete a snapshot file.
        
        Args:
            relative_path: Relative path from snapshots directory
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            full_path = self.snapshots_dir / relative_path
            
            if full_path.exists():
                full_path.unlink()
                logger.debug(f"Deleted snapshot: {relative_path}")
                return True
            else:
                logger.warning(f"Snapshot file not found: {relative_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting snapshot {relative_path}: {e}", exc_info=True)
            return False


# Global snapshot manager instance
snapshot_manager = SnapshotManager()

