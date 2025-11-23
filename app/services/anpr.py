import numpy as np
from typing import Optional
from fast_alpr import ALPR
from app.models.event_models import ANPREvent, ANPRResult
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ANPRDetector:
    """Automatic Number Plate Recognition service using fast-alpr."""
    
    def __init__(self, detector_model: str = "yolo-v9-t-384-license-plate-end2end", 
                 ocr_model: str = "cct-xs-v1-global-model"):
        """
        Initialize ANPR detector using fast-alpr.
        
        Args:
            detector_model: License plate detection model name
            ocr_model: OCR model name for reading plates
        """
        self.detector_model = detector_model
        self.ocr_model = ocr_model
        self.alpr = None
        self._load_model()
    
    def _load_model(self):
        """Load fast-alpr model."""
        try:
            logger.info(f"Loading fast-alpr model (detector: {self.detector_model}, OCR: {self.ocr_model})")
            self.alpr = ALPR(
                detector_model=self.detector_model,
                ocr_model=self.ocr_model
            )
            logger.info("fast-alpr model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load fast-alpr model: {e}")
            raise
    
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
            # Run fast-alpr prediction
            alpr_results = self.alpr.predict(frame)
            
            # Find best license plate candidate
            best_plate = None
            best_confidence = 0.0
            
            # Handle both single result and list of results
            if alpr_results:
                # Convert single result to list for uniform processing
                if not isinstance(alpr_results, list):
                    alpr_results = [alpr_results]
                
                # Process each result
                for result in alpr_results:
                    # fast-alpr returns ALPRResult with ocr and detection attributes
                    # Extract plate text and confidence from ocr result
                    plate_text = None
                    confidence = 0.0
                    
                    # Check for ocr attribute (fast-alpr structure)
                    if hasattr(result, 'ocr'):
                        ocr_result = result.ocr
                        if hasattr(ocr_result, 'text') and hasattr(ocr_result, 'confidence'):
                            plate_text = ocr_result.text
                            confidence = ocr_result.confidence
                        else:
                            logger.warning(f"ANPR: Result ocr missing text or confidence: {ocr_result}")
                    # Fallback: check for direct license_plate and confidence attributes (legacy format)
                    elif hasattr(result, 'license_plate') and hasattr(result, 'confidence'):
                        plate_text = result.license_plate
                        confidence = result.confidence
                    else:
                        logger.warning(f"ANPR: Result missing expected attributes: {result}")
                    
                    # Check confidence threshold and update best plate
                    if plate_text and confidence > confidence_threshold and confidence > best_confidence:
                        best_confidence = confidence
                        best_plate = plate_text
            
            # Return event if plate found
            if best_plate:
                anpr_result = ANPRResult(
                    license_plate=best_plate,
                    confidence=best_confidence,
                    region=None  # fast-alpr may provide region in future versions
                )
                
                return ANPREvent(
                    camera_id=camera_id,
                    anpr_result=anpr_result,
                    frame_number=frame_number
                )
            
            return None
            
        except Exception as e:
            logger.error(f"ANPR detection error for camera {camera_id}: {e}", exc_info=True)
            return None

