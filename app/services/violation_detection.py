import os
import torch
import numpy as np
from typing import List, Optional, Tuple, Dict
from ultralytics import YOLO
from app.utils.logger import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

class ViolationDetector:
    """
    Service for detecting specific violations like No-Helmet, Tripling, and No-Seatbelt.
    """
    
    def __init__(self, helmet_model_instance: Optional[YOLO] = None, tripling_model_instance: Optional[YOLO] = None, seatbelt_model_instance: Optional[YOLO] = None):
        self.helmet_model = helmet_model_instance
        self.tripling_model = tripling_model_instance
        self.seatbelt_model = seatbelt_model_instance
        self.helmet_model_path = settings.helmet_model
        self.tripling_model_path = settings.tripling_model
        self.seatbelt_model_path = settings.seatbelt_model
        
        if not self.helmet_model or not self.tripling_model or not self.seatbelt_model:
            self._load_models()
        
    def _load_models(self):
        """Load violation detection models."""
        try:
            # Check if model files exist
            if not self.helmet_model:
                if os.path.exists(self.helmet_model_path):
                    logger.info(f"Loading Helmet model from: {self.helmet_model_path}")
                    self.helmet_model = YOLO(self.helmet_model_path)
                else:
                    logger.warning(f"Helmet model not found at: {self.helmet_model_path}")
                
            if not self.tripling_model:
                if os.path.exists(self.tripling_model_path):
                    logger.info(f"Loading Tripling model from: {self.tripling_model_path}")
                    self.tripling_model = YOLO(self.tripling_model_path)
                else:
                    logger.warning(f"Tripling model not found at: {self.tripling_model_path}")
            
            if not self.seatbelt_model:
                if os.path.exists(self.seatbelt_model_path):
                    logger.info(f"Loading Seatbelt model from: {self.seatbelt_model_path}")
                    self.seatbelt_model = YOLO(self.seatbelt_model_path)
                else:
                    logger.warning(f"Seatbelt model not found at: {self.seatbelt_model_path}")
                
        except Exception as e:
            logger.error(f"Failed to load violation models: {e}")

    def _is_overlapping(self, box1: List[float], box2: List[float], threshold: float = 0.1) -> bool:
        """
        Check if two boxes overlap.
        box1: [x1, y1, x2, y2] (Violation detection)
        box2: [x1, y1, x2, y2] (Motorcycle/Vehicle)
        """
        # Intersection coordinates
        x_left = max(box1[0], box2[0])
        y_top = max(box1[1], box2[1])
        x_right = min(box1[2], box2[2])
        y_bottom = min(box1[3], box2[3])

        if x_right < x_left or y_bottom < y_top:
            return False

        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        
        # Calculate area of the violation box (box1)
        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        
        if box1_area == 0:
            return False
            
        # Check if intersection is significant relative to the violation box
        # (e.g. is the helmet mostly inside the motorcycle box?)
        # We use a low threshold because sometimes the head is on the edge
        return (intersection_area / box1_area) > threshold

    def check_helmet(self, frame: np.ndarray, bbox: List[float]) -> Tuple[bool, float, str]:
        """
        Check for helmet violation on the frame, scoped to the bbox.
        Returns: (is_violation, confidence, label)
        """
        if self.helmet_model is None:
            return False, 0.0, "model_missing"
            
        try:
            h, w = frame.shape[:2]
            x, y, bw, bh = bbox
            
            # Convert motorcycle bbox to absolute pixel coordinates [x1, y1, x2, y2]
            moto_x1 = int(max(0, x * w))
            moto_y1 = int(max(0, y * h))
            moto_x2 = int(min(w, (x + bw) * w))
            moto_y2 = int(min(h, (y + bh) * h))
            moto_box = [moto_x1, moto_y1, moto_x2, moto_y2]
            
            # Run inference on the FULL frame
            results = self.helmet_model(frame, verbose=False)
            
            for result in results:
                boxes = result.boxes
                logger.debug(f"Helmet Model Raw Results: {len(boxes)} detections in full frame")
                
                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i])
                    conf = float(boxes.conf[i])
                    label = self.helmet_model.names[cls_id]
                    
                    # Get detection box [x1, y1, x2, y2]
                    det_box = boxes.xyxy[i].tolist()
                    
                    # Helmet Model Classes: 0: Helmet, 1: No-helmet, 2: Person, 3: vehicle
                    # We look for "No-helmet" (Class 1)
                    if label == "No-helmet" and conf > 0.3:
                        # Check if this detection belongs to our motorcycle
                        if self._is_overlapping(det_box, moto_box):
                            logger.info(f"VIOLATION DETECTED: No-helmet with confidence {conf} (overlaps with motorcycle)")
                            return True, conf, "no_helmet"
                        else:
                            logger.debug(f"Ignored No-helmet detection at {det_box} - outside motorcycle bbox {moto_box}")
                        
            return False, 0.0, "helmet_compliant"
            
        except Exception as e:
            logger.error(f"Error checking helmet violation: {e}", exc_info=True)
            return False, 0.0, "error"

    def check_tripling(self, frame: np.ndarray, bbox: List[float]) -> Tuple[bool, float, str]:
        """
        Check for tripling violation on the frame, scoped to the bbox.
        Returns: (is_violation, confidence, label)
        """
        if self.tripling_model is None:
            return False, 0.0, "model_missing"
            
        try:
            h, w = frame.shape[:2]
            x, y, bw, bh = bbox
            
            # Convert motorcycle bbox to absolute pixel coordinates [x1, y1, x2, y2]
            moto_x1 = int(max(0, x * w))
            moto_y1 = int(max(0, y * h))
            moto_x2 = int(min(w, (x + bw) * w))
            moto_y2 = int(min(h, (y + bh) * h))
            moto_box = [moto_x1, moto_y1, moto_x2, moto_y2]
            
            # Run inference on the FULL frame
            results = self.tripling_model(frame, verbose=False)
            
            for result in results:
                boxes = result.boxes
                logger.debug(f"Tripling Model Raw Results: {len(boxes)} detections in full frame")
                
                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i])
                    conf = float(boxes.conf[i])
                    label = self.tripling_model.names[cls_id]
                    
                    # Get detection box [x1, y1, x2, y2]
                    det_box = boxes.xyxy[i].tolist()
                    
                    # Tripling Model Classes: 0: non-offender, 1: offender
                    if label == "offender" and conf > 0.3:
                         # Check if this detection belongs to our motorcycle
                        if self._is_overlapping(det_box, moto_box):
                            logger.info(f"VIOLATION DETECTED: Tripling with confidence {conf} (overlaps with motorcycle)")
                            return True, conf, "tripling"
                        else:
                            logger.debug(f"Ignored Tripling detection at {det_box} - outside motorcycle bbox {moto_box}")
                        
            return False, 0.0, "tripling_compliant"
            
        except Exception as e:
            logger.error(f"Error checking tripling violation: {e}", exc_info=True)
            return False, 0.0, "error"

    def check_seatbelt(self, frame: np.ndarray, bbox: List[float]) -> Tuple[bool, float, str]:
        """
        Check for seatbelt violation on the frame, scoped to the bbox.
        Returns: (is_violation, confidence, label)
        
        Model outputs:
        - car (ID: 0)
        - no seat-belt (ID: 1) - This is the violation
        - windshield (ID: 2)
        """
        if self.seatbelt_model is None:
            return False, 0.0, "model_missing"
            
        try:
            h, w = frame.shape[:2]
            x, y, bw, bh = bbox
            
            # Convert vehicle bbox to absolute pixel coordinates [x1, y1, x2, y2]
            vehicle_x1 = int(max(0, x * w))
            vehicle_y1 = int(max(0, y * h))
            vehicle_x2 = int(min(w, (x + bw) * w))
            vehicle_y2 = int(min(h, (y + bh) * h))
            vehicle_box = [vehicle_x1, vehicle_y1, vehicle_x2, vehicle_y2]
            
            # Run inference on the FULL frame
            results = self.seatbelt_model(frame, verbose=False)
            
            for result in results:
                boxes = result.boxes
                logger.debug(f"Seatbelt Model Raw Results: {len(boxes)} detections in full frame")
                
                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i])
                    conf = float(boxes.conf[i])
                    label = self.seatbelt_model.names[cls_id]
                    
                    # Get detection box [x1, y1, x2, y2]
                    det_box = boxes.xyxy[i].tolist()
                    
                    # Seatbelt Model Classes: 0: car, 1: no seat-belt, 2: windshield
                    # We look for "no seat-belt" (Class 1)
                    if label == "no seat-belt" and conf > 0.3:
                        # Check if this detection belongs to our vehicle
                        if self._is_overlapping(det_box, vehicle_box):
                            logger.info(f"VIOLATION DETECTED: No seatbelt with confidence {conf} (overlaps with vehicle)")
                            return True, conf, "no_seatbelt"
                        else:
                            logger.debug(f"Ignored No-seatbelt detection at {det_box} - outside vehicle bbox {vehicle_box}")
                        
            return False, 0.0, "seatbelt_compliant"
            
        except Exception as e:
            logger.error(f"Error checking seatbelt violation: {e}", exc_info=True)
            return False, 0.0, "error"
