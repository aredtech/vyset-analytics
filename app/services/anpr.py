import easyocr
import numpy as np
import re
from typing import Optional, List
from app.models.event_models import ANPREvent, ANPRResult
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ANPRDetector:
    """Automatic Number Plate Recognition service."""
    
    def __init__(self, languages: List[str] = None):
        """
        Initialize ANPR detector.
        
        Args:
            languages: List of languages for OCR (default: ['en'])
        """
        self.languages = languages or ['en']
        self.reader = None
        self._load_model()
    
    def _load_model(self):
        """Load EasyOCR model."""
        try:
            logger.info(f"Loading EasyOCR model for languages: {self.languages}")
            self.reader = easyocr.Reader(self.languages, gpu=False)
            logger.info("EasyOCR model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load EasyOCR model: {e}")
            raise
    
    def _is_valid_plate(self, text: str) -> bool:
        """
        Check if text looks like a license plate.
        
        Args:
            text: OCR text result
            
        Returns:
            True if text looks like a license plate
        """
        # Remove spaces and special characters
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        
        # Basic validation: 4-8 characters, mix of letters and numbers
        if len(cleaned) < 4 or len(cleaned) > 8:
            return False
        
        has_letter = bool(re.search(r'[A-Z]', cleaned))
        has_number = bool(re.search(r'[0-9]', cleaned))
        
        return has_letter and has_number
    
    def detect(
        self,
        frame: np.ndarray,
        camera_id: str,
        frame_number: int,
        confidence_threshold: float = 0.5
    ) -> Optional[ANPREvent]:
        """
        Detect license plates in a frame.
        
        Args:
            frame: Input frame (numpy array)
            camera_id: Camera identifier
            frame_number: Frame number
            confidence_threshold: Minimum confidence threshold
            
        Returns:
            ANPREvent if plate detected, None otherwise
        """
        try:
            # Run OCR
            results = self.reader.readtext(frame)
            
            # Find best license plate candidate
            best_plate = None
            best_confidence = 0.0
            
            for (bbox, text, conf) in results:
                # Check if looks like a license plate
                if self._is_valid_plate(text) and conf > confidence_threshold:
                    if conf > best_confidence:
                        best_confidence = conf
                        # Clean up the text
                        cleaned_text = re.sub(r'[^A-Z0-9]', '', text.upper())
                        best_plate = cleaned_text
            
            # Return event if plate found
            if best_plate:
                anpr_result = ANPRResult(
                    license_plate=best_plate,
                    confidence=best_confidence,
                    region=None  # Can be enhanced with region detection
                )
                
                return ANPREvent(
                    camera_id=camera_id,
                    anpr_result=anpr_result,
                    frame_number=frame_number
                )
            
            return None
            
        except Exception as e:
            logger.error(f"ANPR detection error for camera {camera_id}: {e}")
            return None

