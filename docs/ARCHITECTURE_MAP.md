# Vyset Analytics — Architecture Map: Frame Processing & Models

This document describes how video frames flow through the system and how each type of model is used.

---

## 1. High-Level Frame Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CAMERA STREAM (RTSP / HTTP / File)                      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  CameraWorker._process_stream()                                                   │
│  • cv2.VideoCapture(stream_url) → ret, frame                                     │
│  • Frame skip (config: frame_skip)                                                │
│  • FPS cap (config: max_fps)                                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  CameraWorker._process_frame(frame)  ←── ONE FRAME (numpy array BGR)             │
│                                                                                   │
│  Order of execution (all optional, per-camera config):                            │
│    1. Geofence mandatory capture check (one-time signal timeout)                  │
│    2. Object detection (YOLO general) → tracking events, vehicles_detected        │
│    3. Motion detection (OpenCV)                                                   │
│    4. Garbage detection (YOLO garbage)                                            │
│    5. ANPR (fast-alpr) — only if vehicles_detected == True                        │
└─────────────────────────────────────────────────────────────────────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
            ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
            │ EventFilter   │   │ Snapshot      │   │ save_and_      │
            │ (cooldown)    │   │ Manager       │   │ publish_event  │
            └───────────────┘   └───────────────┘   └───────────────┘
                                                              │
                                                              ▼
                                            ┌─────────────────────────────┐
                                            │ PostgreSQL + Redis Pub/Sub   │
                                            └─────────────────────────────┘
```

---

## 2. Models Used by Detection Type

| Detection Type     | Model / Algorithm | Weights / Config | Service Class    | Output Events |
|--------------------|-------------------|------------------|------------------|---------------|
| **Object detection** | YOLOv8 (Ultralytics) | `yolo_model` → `/app/weights/general/yolov8m.pt` | `ObjectDetector` (`app/services/detection.py`) | `tracking` (entered/left) |
| **Motion**         | OpenCV MOG2 background subtractor | No weights; `motion_threshold` in config | `MotionDetector` (`app/services/motion.py`) | `motion` |
| **Garbage**        | Custom YOLO (Ultralytics) | `garbage_model` → `/app/weights/garbage_detection/best.pt` | `GarbageDetector` (+ optional `GarbageTracker`) (`app/services/garbage_detection.py`, `garbage_tracker.py`) | `detection` or `tracking` |
| **ANPR**           | fast-alpr (YOLO-v9 LP detector + CCT OCR) | Detector: `yolo-v9-t-384-license-plate-end2end`, OCR: `cct-xs-v1-global-model` | `ANPRDetector` (`app/services/anpr.py`) | `anpr` |

---

## 3. Per-Frame Processing Order (Detail)

```
_process_frame(frame)
│
├─► [Optional] Geofence one-time signal: if no analytics event yet and timeout → save "geofence_capture"
│
├─► OBJECT DETECTION (if enable_object_detection)
│   • ObjectDetector.detect(frame) → YOLO infer + ByteTrack
│   • Model: YOLOv8 (yolov8m.pt), target_classes from config (e.g. person, car, truck)
│   • Output: list of TrackingEvent (entered / left)
│   • Sets vehicles_detected = True if any vehicle class in events or active_tracks
│   • Each event → EventFilter.should_publish_tracking → snapshot → save_and_publish_event("tracking")
│
├─► MOTION DETECTION (if enable_motion_detection)
│   • MotionDetector.detect(frame) → OpenCV MOG2 + frame diff
│   • No neural network; background subtractor + threshold
│   • Output: MotionEvent (motion_intensity, affected_area_percentage) or None
│   • If event: EventFilter.should_publish_motion → save_motion_snapshot → save_and_publish_event("motion")
│
├─► GARBAGE DETECTION (if enable_garbage_detection)
│   • GarbageDetector.detect(frame) → YOLO garbage model (and optionally ByteTrack via GarbageTracker)
│   • Model: custom YOLO (best.pt), classes: garbage, trash, litter, waste, etc.
│   • If enable_garbage_tracking: list of TrackingEvent → save_and_publish_event("tracking")
│   • Else: DetectionEvent → save_and_publish_event("detection")
│
└─► ANPR (if enable_anpr and vehicles_detected)
    • ANPRDetector.detect(frame) → fast-alpr (LP detector + OCR)
    • Only runs when object detector has seen a vehicle (car, truck, bus, etc.)
    • Output: ANPREvent (license_plate, confidence) or None
    • If event: EventFilter.should_publish_anpr → save_anpr_snapshot → save_and_publish_event("anpr")
```

---

## 4. Model Dependency Diagram

```
                    ┌──────────────────────────────────────┐
                    │           Raw frame (BGR)             │
                    └──────────────────────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
         ▼                             ▼                             ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ ObjectDetector  │         │ MotionDetector  │         │ GarbageDetector  │
│ YOLOv8 (general)│         │ OpenCV MOG2     │         │ YOLO (garbage)   │
│ yolov8m.pt      │         │ (no weights)    │         │ best.pt          │
│ + ByteTrack     │         │                 │         │ ± ByteTrack      │
└────────┬────────┘         └────────┬────────┘         └────────┬────────┘
         │                           │                           │
         │ vehicles_detected          │                           │
         │ (vehicle classes)         │                           │
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ tracking events │         │ motion event    │         │ detection /     │
│ (entered/left)  │         │                 │         │ tracking events │
└────────┬────────┘         └────────┬────────┘         └────────┬────────┘
         │                           │                           │
         │  when vehicles_detected   │                           │
         ▼                           │                           │
┌─────────────────┐                 │                           │
│ ANPRDetector    │                 │                           │
│ fast-alpr       │                 │                           │
│ (LP + OCR)      │                 │                           │
└────────┬────────┘                 │                           │
         │                           │                           │
         ▼                           │                           │
┌─────────────────┐                 │                           │
│ anpr event      │                 │                           │
└────────┬────────┘                 │                           │
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     ▼
                    ┌──────────────────────────────────────┐
                    │  EventFilter → Snapshot → DB + Redis  │
                    └──────────────────────────────────────┘
```

---

## 5. Configuration Summary (Models)

| Config / Env | Default | Used by |
|-------------|---------|---------|
| `yolo_model` | `/app/weights/general/yolov8m.pt` | ObjectDetector (general objects + vehicles) |
| `garbage_model` | `/app/weights/garbage_detection/best.pt` | GarbageDetector / GarbageTracker |
| ANPR detector | `yolo-v9-t-384-license-plate-end2end` | ANPRDetector (fast-alpr) |
| ANPR OCR | `cct-xs-v1-global-model` | ANPRDetector (fast-alpr) |

Per-camera flags (from `CameraConfig.parameters`):

- `enable_object_detection`, `enable_motion_detection`, `enable_garbage_detection`, `enable_anpr`
- `detection_classes` (for object detector)
- `enable_object_tracking`, `enable_garbage_tracking` (ByteTrack)
- `confidence_threshold`, `garbage_confidence_threshold`, `motion_threshold`

---

## 6. File Reference

| Component | File |
|-----------|------|
| Frame loop & detector orchestration | `app/services/video_worker.py` |
| General object detection (YOLO + ByteTrack) | `app/services/detection.py` |
| Motion (OpenCV) | `app/services/motion.py` |
| Garbage (YOLO ± ByteTrack) | `app/services/garbage_detection.py`, `app/services/garbage_tracker.py` |
| ANPR (fast-alpr) | `app/services/anpr.py` |
| Event cooldown filtering | `app/services/event_filter.py` |
| Model paths | `app/core/config.py` |

---

*Generated for Vyset Analytics. Weights under `app/weights/helmet/` and `app/weights/tripling/` exist on disk but are not currently wired into the pipeline.*
