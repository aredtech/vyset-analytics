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

    def detect_violations(self, frame: np.ndarray, model_type: str) -> List[Dict]:
        """
        Run inference on the full frame and return all relevant detections.
        
        Args:
            frame: Input frame
            model_type: 'helmet' or 'tripling'
            
        Returns:
            List of dictionaries containing:
            - box: [x1, y1, x2, y2]
            - confidence: float
            - label: str
        """
        detections = []
        
        if model_type == "helmet":
            model = self.helmet_model
            target_label = "No-helmet"
        elif model_type == "tripling":
            model = self.tripling_model
            target_label = "offender"
        else:
            logger.error(f"Unknown model type: {model_type}")
            return []
            
        if model is None:
            return []
            
        try:
            # Run inference on the FULL frame
            results = model(frame, verbose=False)
            
            for result in results:
                boxes = result.boxes
                
                # DEBUG: Log all detected classes to verify mapping
                if len(boxes) > 0:
                    unique_labels = set()
                    for i in range(len(boxes)):
                        unique_labels.add(model.names[int(boxes.cls[i])])
                    logger.info(f"DEBUG: {model_type} model found classes in frame: {unique_labels}")

                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i])
                    conf = float(boxes.conf[i])
                    label = model.names[cls_id]
                    det_box = boxes.xyxy[i].tolist() # [x1, y1, x2, y2]
                    
                    # Log potential candidates even if confidence is low, for debugging
                    if label == target_label:
                         logger.info(f"DEBUG: Found {label} with confidence {conf:.2f} at {det_box}")

                    if label == target_label and conf > 0.2:
                        detections.append({
                            "box": det_box,
                            "confidence": conf,
                            "label": label,
                            "type": "no_helmet" if model_type == "helmet" else "tripling"
                        })
                        
            return detections
            
        except Exception as e:
            logger.error(f"Error in {model_type} detection: {e}", exc_info=True)
            return []

    # Keeping old methods for backward compatibility if needed, but they are inefficient
    # The video_worker will be updated to use detect_violations instead.

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

    def check_seatbelt(self, frame: np.ndarray, bbox: Optional[List[float]] = None) -> Tuple[bool, float, str]:
        """
        Check for seatbelt violation on the frame.
        
        Args:
            frame: Input image (full frame or crop)
            bbox: Bounding box [x, y, w, h] normalized (0-1). 
                  If None, assumes the entire frame is the vehicle (used when passing cropped vehicle images).
                  
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
            
            # If bbox is provided, use it. If not, assume full frame (crop mode)
            if bbox:
                x, y, bw, bh = bbox
                # Convert vehicle bbox to absolute pixel coordinates [x1, y1, x2, y2]
                vehicle_x1 = int(max(0, x * w))
                vehicle_y1 = int(max(0, y * h))
                vehicle_x2 = int(min(w, (x + bw) * w))
                vehicle_y2 = int(min(h, (y + bh) * h))
            else:
                vehicle_x1, vehicle_y1 = 0, 0
                vehicle_x2, vehicle_y2 = w, h
                
            vehicle_box = [vehicle_x1, vehicle_y1, vehicle_x2, vehicle_y2]
            
            # Run inference on the frame
            results = self.seatbelt_model(frame, verbose=False)
            
            windshield_detected = False
            seatbelt_violation_conf = 0.0
            seatbelt_violation_box = None
            
            # First pass: Check for windshield and potential seatbelt violation
            for result in results:
                boxes = result.boxes
                
                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i])
                    conf = float(boxes.conf[i])
                    label = self.seatbelt_model.names[cls_id]
                    det_box = boxes.xyxy[i].tolist()
                    
                    # Check for Windshield (Class 2)
                    if label == "windshield" and conf > 0.3:
                         if self._is_overlapping(det_box, vehicle_box):
                            windshield_detected = True
                            logger.debug(f"Windshield detected with confidence {conf}")

                    # Check for No Seatbelt (Class 1)
                    if label == "no seat-belt" and conf > 0.3:
                        if self._is_overlapping(det_box, vehicle_box):
                            # Store the highest confidence violation found
                            if conf > seatbelt_violation_conf:
                                seatbelt_violation_conf = conf
                                seatbelt_violation_box = det_box
            
            # Logic Update: Relaxed Windshield Requirement
            # If we see "no seat-belt" with high confidence (>0.5), we report it even without windshield.
            # If confidence is lower (0.3-0.5), we require windshield to potential false positives.
            
            if seatbelt_violation_conf > 0.5:
                logger.info(f"VIOLATION DETECTED: No seatbelt with high confidence {seatbelt_violation_conf} (Windshield check skipped)")
                return True, seatbelt_violation_conf, "no_seatbelt"
                
            elif seatbelt_violation_conf > 0.3 and windshield_detected:
                logger.info(f"VIOLATION DETECTED: No seatbelt with confidence {seatbelt_violation_conf} (Windshield confirmed)")
                return True, seatbelt_violation_conf, "no_seatbelt"
                
            elif seatbelt_violation_conf > 0:
                logger.debug(f"Ignored low confidence No-seatbelt detection ({seatbelt_violation_conf}) - Windshield NOT detected")
                return False, 0.0, "seatbelt_compliant_low_conf"
                        
            return False, 0.0, "seatbelt_compliant"
            
        except Exception as e:
            logger.error(f"Error checking seatbelt violation: {e}", exc_info=True)
            return False, 0.0, "error"
