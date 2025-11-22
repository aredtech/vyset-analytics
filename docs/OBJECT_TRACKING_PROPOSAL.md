# Object Tracking-Based Event Filtering - Implementation Proposal

## Overview

This document proposes replacing time-based event filtering with **object tracking-based filtering** for more intelligent and accurate event detection.

## Current Limitation

The existing time-based filtering has a fundamental limitation:

```python
# Current approach
Frame 1: 2 persons detected → Event published
Frame 50: 2 persons detected → Filtered (cooldown)
Frame 100: 2 persons detected → Filtered (no change)

# Problem: Can't tell if these are the SAME 2 people or different people!
```

**Scenarios it can't handle well:**
1. Person A leaves, Person B enters → Still "2 persons", no event!
2. Car parks, different car takes the spot → Same count, missed!
3. Person walks through, comes back 20 seconds later → Treated as same presence

## Proposed Solution: Object Tracking

Assign **unique IDs** to each detected object and track them across frames.

```python
# With object tracking
Frame 1: Person enters (ID: 1) → Event: "Person 1 entered"
Frame 50: Person 1 still present → No event (same object)
Frame 100: Person 1 leaves → Event: "Person 1 left"
Frame 150: Person enters (ID: 2) → Event: "Person 2 entered"  # Different person!
```

## Benefits

1. ✅ **Accurate Entry/Exit Events** - Know exactly when objects enter/leave
2. ✅ **Individual Tracking** - Track each object separately
3. ✅ **No False Negatives** - Detect when objects are swapped
4. ✅ **Object Trajectories** - Can track movement paths
5. ✅ **Re-identification** - Detect when same object returns
6. ✅ **Dwell Time** - Know how long each object stayed
7. ✅ **Counting Accuracy** - Precise people/vehicle counting

## Implementation Architecture

### Option 1: ByteTrack (Recommended)

**Pros:**
- Fast (minimal overhead)
- Simple integration with YOLO
- Good accuracy for most use cases
- Open source, active development

**Cons:**
- Less robust in very crowded scenes
- No re-identification across occlusions

**Performance:**
- CPU: +5-10% overhead
- Memory: +50MB per camera
- Latency: +2-5ms per frame

### Option 2: DeepSORT

**Pros:**
- Excellent re-identification
- Handles occlusions well
- Industry standard

**Cons:**
- Requires additional deep learning model
- Higher CPU/memory usage
- More complex setup

**Performance:**
- CPU: +15-25% overhead
- Memory: +150MB per camera
- Latency: +10-20ms per frame

### Option 3: BoT-SORT

**Pros:**
- State-of-the-art accuracy
- Best for complex scenarios
- Good re-identification

**Cons:**
- Highest resource usage
- Most complex implementation

**Performance:**
- CPU: +20-30% overhead
- Memory: +200MB per camera
- Latency: +15-30ms per frame

## Recommended Approach: ByteTrack + Ultralytics

Ultralytics YOLOv8 has **built-in tracking** using ByteTrack!

```python
# Simple integration - just add track=True
results = model.track(frame, persist=True)

# Each detection now has a unique tracking ID
for result in results:
    boxes = result.boxes
    for box in boxes:
        track_id = int(box.id[0])  # Unique ID across frames!
        class_name = model.names[int(box.cls[0])]
        confidence = float(box.conf[0])
```

**This is already available in our YOLO models!** 🎉

## Proposed Implementation

### 1. New Model: TrackedDetection

```python
class TrackedDetection(BaseModel):
    """Single tracked object detection."""
    track_id: int                    # Unique tracking ID
    class_name: str
    confidence: float
    bounding_box: BoundingBox
    first_seen_frame: int           # When object first appeared
    last_seen_frame: int            # Last frame where detected
    is_new: bool = False            # True if just entered scene
    is_leaving: bool = False        # True if just left scene
```

### 2. New Model: TrackingEvent

```python
class TrackingEvent(BaseModel):
    """Event for tracked object lifecycle."""
    event_type: str = "tracking"
    camera_id: str
    timestamp: str
    track_id: int
    class_name: str
    action: str  # "entered", "left", "updated"
    dwell_time_seconds: Optional[float] = None  # For "left" events
    trajectory: Optional[List[BoundingBox]] = None  # Path through scene
```

### 3. Enhanced ObjectDetector

```python
class ObjectDetector:
    def __init__(self, model_path: str, enable_tracking: bool = True):
        self.model = YOLO(model_path)
        self.enable_tracking = enable_tracking
        self.active_tracks = {}  # track_id -> track info
    
    def detect(self, frame, camera_id, frame_number, **kwargs):
        if self.enable_tracking:
            # Use built-in tracking
            results = self.model.track(frame, persist=True, verbose=False)
            return self._process_tracked_results(results, camera_id, frame_number)
        else:
            # Standard detection (current behavior)
            results = self.model(frame, verbose=False)
            return self._process_results(results, camera_id, frame_number)
    
    def _process_tracked_results(self, results, camera_id, frame_number):
        current_tracks = set()
        events = []
        
        for result in results:
            boxes = result.boxes
            
            for i in range(len(boxes)):
                # Extract tracking info
                track_id = int(boxes.id[i]) if boxes.id is not None else None
                if track_id is None:
                    continue
                
                current_tracks.add(track_id)
                class_name = self.model.names[int(boxes.cls[i])]
                confidence = float(boxes.conf[i])
                
                # Check if this is a new object
                if track_id not in self.active_tracks:
                    # NEW OBJECT ENTERED
                    self.active_tracks[track_id] = {
                        'class_name': class_name,
                        'first_seen': frame_number,
                        'last_seen': frame_number
                    }
                    
                    # Generate entry event
                    event = TrackingEvent(
                        camera_id=camera_id,
                        track_id=track_id,
                        class_name=class_name,
                        action="entered"
                    )
                    events.append(event)
                else:
                    # Update existing track
                    self.active_tracks[track_id]['last_seen'] = frame_number
        
        # Check for objects that left (no longer in current_tracks)
        for track_id in list(self.active_tracks.keys()):
            if track_id not in current_tracks:
                # OBJECT LEFT
                track_info = self.active_tracks[track_id]
                dwell_time = (frame_number - track_info['first_seen']) / 30.0  # Assume 30 FPS
                
                event = TrackingEvent(
                    camera_id=camera_id,
                    track_id=track_id,
                    class_name=track_info['class_name'],
                    action="left",
                    dwell_time_seconds=dwell_time
                )
                events.append(event)
                
                # Remove from active tracks
                del self.active_tracks[track_id]
        
        return events
```

### 4. Updated CameraParameters

```python
class CameraParameters(BaseModel):
    # ... existing fields ...
    
    # Tracking settings
    enable_object_tracking: bool = True
    tracking_confidence_threshold: float = 0.3
    track_buffer_frames: int = 30  # Frames to wait before declaring object "left"
    min_dwell_time_seconds: float = 1.0  # Minimum time to trigger "left" event
```

## Event Flow Comparison

### Current Time-Based Approach

```
00:00 - Person A enters
00:00 - Detection: 1 person → EVENT PUBLISHED
00:01 - Person A still there → Filtered (cooldown)
00:05 - Person A still there → Filtered (no change)
00:06 - Person A leaves, Person B enters
00:06 - Detection: 1 person → Filtered (no change - still 1 person!)
```

❌ **Problem**: Missed that Person A left and Person B entered!

### Proposed Tracking-Based Approach

```
00:00 - Track ID 1 appears (Person A) → EVENT: "Person entered (ID: 1)"
00:01 - Track ID 1 still present → No event
00:05 - Track ID 1 still present → No event
00:06 - Track ID 1 disappears → EVENT: "Person left (ID: 1, dwell: 6s)"
00:06 - Track ID 2 appears (Person B) → EVENT: "Person entered (ID: 2)"
```

✅ **Success**: Detected both exit and entry!

## Use Cases That Become Possible

### 1. Accurate People Counting
```python
# Know exact count at any moment
entered_today = count(action="entered", date=today)
left_today = count(action="left", date=today)
current_occupancy = entered_today - left_today
```

### 2. Dwell Time Analytics
```python
# Average time people spend in area
avg_dwell = average(dwell_time_seconds where action="left")

# Detect loitering
loiterers = filter(dwell_time_seconds > 300)  # > 5 minutes
```

### 3. Object Persistence
```python
# Same car parking multiple times
car_visits = group_by(track_id, class_name="car")

# Frequent visitors (could be combined with ANPR)
frequent = filter(count(track_id) > 5)
```

### 4. Traffic Flow Analysis
```python
# Direction of movement (trajectory analysis)
entry_zone = ROI("entrance")
exit_zone = ROI("exit")

entering = filter(first_bounding_box in entry_zone)
exiting = filter(last_bounding_box in exit_zone)
```

### 5. Abandonment Detection
```python
# Object appears but doesn't leave (abandoned bag/vehicle)
stationary = filter(
    dwell_time_seconds > 600,  # 10 minutes
    movement_distance < 0.1  # Didn't move much
)
```

## Migration Strategy

### Phase 1: Add Tracking (Backward Compatible)
- Add tracking capability to ObjectDetector
- Keep existing time-based filtering as default
- Add `enable_object_tracking` parameter (default: False)

### Phase 2: Run Both Systems in Parallel
- Emit both time-based and tracking-based events
- Compare accuracy and performance
- Tune tracking parameters

### Phase 3: Switch Default to Tracking
- Make tracking the default
- Keep time-based as fallback option
- Update documentation

### Phase 4: Deprecate Time-Based (Optional)
- Remove time-based filtering after stability proven
- Or keep both as options

## Configuration Example

```json
{
  "camera_id": "entrance-cam",
  "stream_url": "rtsp://camera/stream",
  "parameters": {
    "enable_object_detection": true,
    "enable_object_tracking": true,
    
    // Tracking settings
    "tracking_confidence_threshold": 0.3,
    "track_buffer_frames": 30,
    "min_dwell_time_seconds": 2.0,
    
    // Fallback to time-based if needed
    "detection_cooldown_seconds": 5.0
  }
}
```

## Performance Considerations

### CPU Usage
- ByteTrack: +5-10% per camera
- Acceptable for most deployments

### Memory Usage
- ~50MB per camera for tracking state
- Grows with number of simultaneous objects
- Cleanup inactive tracks after N frames

### Accuracy
- Much better than time-based
- Fewer false positives
- Fewer false negatives
- More meaningful events

## Implementation Effort

### Easy (2-3 hours)
Using YOLO's built-in tracking:
1. Modify `ObjectDetector.detect()` to use `model.track()`
2. Add track ID to Detection model
3. Track active IDs in CameraWorker
4. Emit events on ID appear/disappear

### Medium (1 day)
Full implementation with:
1. New TrackedDetection and TrackingEvent models
2. Tracking state management
3. Dwell time calculation
4. Configuration parameters
5. Documentation

### Advanced (2-3 days)
With additional features:
1. Trajectory tracking
2. Zone-based events (enter/exit specific areas)
3. Re-identification across cameras
4. Analytics dashboard
5. Historical tracking data storage

## Recommendation

**Implement the Medium approach** with ByteTrack:

1. ✅ Leverage YOLO's built-in tracking (already there!)
2. ✅ Much more accurate than time-based
3. ✅ Reasonable performance overhead
4. ✅ Enables advanced analytics
5. ✅ Industry-standard approach

**Next Steps:**
1. Implement tracking in ObjectDetector
2. Add TrackedDetection and TrackingEvent models
3. Update event filtering logic
4. Test with real cameras
5. Compare with time-based approach
6. Roll out gradually

## Code Example: Quick Integration

Here's how simple it could be with YOLO's built-in tracking:

```python
# In detection.py - minimal change!
def detect(self, frame, camera_id, frame_number, **kwargs):
    # Just change this line:
    results = self.model.track(frame, persist=True, verbose=False)  # Was: self.model(frame)
    
    # Now boxes have .id attribute!
    for result in results:
        boxes = result.boxes
        for i in range(len(boxes)):
            track_id = int(boxes.id[i]) if boxes.id is not None else None
            # ... rest of processing ...
```

**That's it!** The hard work is already done by Ultralytics. We just need to use the tracking IDs.

## Conclusion

Object tracking is **significantly better** than time-based filtering because:

1. 🎯 **More Accurate** - Knows exactly when objects enter/leave
2. 🚀 **Enables New Features** - Counting, dwell time, trajectories
3. 💡 **Smarter Events** - No false positives from count coincidences
4. 📊 **Better Analytics** - Individual object lifecycle data
5. ⚡ **Easy to Implement** - YOLO has built-in tracking!

**Recommendation**: Implement this as the next major improvement to the analytics service.

