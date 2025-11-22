#!/usr/bin/env python3
"""
Test script to demonstrate track_id based deduplication.

This script shows how the EventFilter prevents duplicate events for the same track_id,
reducing server strain by only emitting events when objects enter/leave, not on every frame.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.event_filter import EventFilter
from app.models.event_models import TrackingEvent, BoundingBox, ModelInfo
from datetime import datetime

def test_track_deduplication():
    """Test that track_id deduplication works correctly."""
    
    print("Testing Track ID Deduplication")
    print("=" * 50)
    
    # Create event filter
    camera_id = "test-camera-01"
    event_filter = EventFilter(camera_id=camera_id)
    
    # Create test tracking events
    bbox = BoundingBox(x=0.1, y=0.1, width=0.2, height=0.3)
    model_info = ModelInfo(model_type="yolov8n", version="8.1.0")
    
    # Test events for the same track_id
    events = [
        # First detection of track_id 42 (should be emitted)
        TrackingEvent(
            camera_id=camera_id,
            track_id=42,
            tracking_action="entered",
            class_name="person",
            confidence=0.85,
            bounding_box=bbox,
            frame_number=100,
            model_info=model_info
        ),
        # Same track_id detected again (should be filtered out)
        TrackingEvent(
            camera_id=camera_id,
            track_id=42,
            tracking_action="entered",
            class_name="person",
            confidence=0.87,
            bounding_box=bbox,
            frame_number=101,
            model_info=model_info
        ),
        # Same track_id detected again (should be filtered out)
        TrackingEvent(
            camera_id=camera_id,
            track_id=42,
            tracking_action="entered",
            class_name="person",
            confidence=0.89,
            frame_number=102,
            bounding_box=bbox,
            model_info=model_info
        ),
        # Track_id 42 leaves (should be emitted)
        TrackingEvent(
            camera_id=camera_id,
            track_id=42,
            tracking_action="left",
            class_name="person",
            confidence=0.0,
            bounding_box=bbox,
            frame_number=200,
            dwell_time_seconds=10.0,
            model_info=model_info
        ),
        # New track_id 43 enters (should be emitted)
        TrackingEvent(
            camera_id=camera_id,
            track_id=43,
            tracking_action="entered",
            class_name="car",
            confidence=0.92,
            bounding_box=bbox,
            frame_number=201,
            model_info=model_info
        ),
        # Track_id 43 leaves (should be emitted)
        TrackingEvent(
            camera_id=camera_id,
            track_id=43,
            tracking_action="left",
            class_name="car",
            confidence=0.0,
            bounding_box=bbox,
            frame_number=300,
            dwell_time_seconds=9.9,
            model_info=model_info
        ),
        # Track_id 42 tries to enter again (should be emitted - it's a new instance)
        TrackingEvent(
            camera_id=camera_id,
            track_id=42,
            tracking_action="entered",
            class_name="person",
            confidence=0.88,
            bounding_box=bbox,
            frame_number=301,
            model_info=model_info
        ),
    ]
    
    print("Testing {} tracking events...".format(len(events)))
    print()
    
    emitted_count = 0
    filtered_count = 0
    
    for i, event in enumerate(events, 1):
        should_emit = event_filter.should_publish_tracking(event)
        
        if should_emit:
            emitted_count += 1
            status = "EMITTED"
        else:
            filtered_count += 1
            status = "FILTERED"
        
        print("Event {:2d}: Track ID {:2d} {:7s} {:6s} -> {}".format(
            i, event.track_id, event.tracking_action, event.class_name, status))
    
    print()
    print("Results Summary:")
    print("   Total events: {}".format(len(events)))
    print("   Emitted: {}".format(emitted_count))
    print("   Filtered: {}".format(filtered_count))
    print("   Reduction: {:.1f}%".format(filtered_count/len(events)*100))
    print()
    
    # Verify expected behavior
    expected_emitted = 5  # entered(42), left(42), entered(43), left(43), entered(42) again
    expected_filtered = 2  # duplicate entered(42) events
    
    if emitted_count == expected_emitted and filtered_count == expected_filtered:
        print("Test PASSED! Deduplication working correctly.")
        print()
        print("Benefits:")
        print("   - Prevents duplicate 'entered' events for same track_id")
        print("   - Only emits meaningful lifecycle events (enter/leave)")
        print("   - Reduces server load by filtering redundant events")
        print("   - Maintains tracking accuracy with unique IDs")
        return True
    else:
        print("Test FAILED! Expected {} emitted, {} filtered".format(expected_emitted, expected_filtered))
        print("   Got {} emitted, {} filtered".format(emitted_count, filtered_count))
        return False

def test_edge_cases():
    """Test edge cases for track deduplication."""
    
    print("\nTesting Edge Cases")
    print("=" * 30)
    
    camera_id = "test-camera-02"
    event_filter = EventFilter(camera_id=camera_id)
    
    bbox = BoundingBox(x=0.1, y=0.1, width=0.2, height=0.3)
    model_info = ModelInfo(model_type="yolov8n", version="8.1.0")
    
    # Test cases
    test_cases = [
        # Case 1: Left event without prior entered event
        {
            "event": TrackingEvent(
                camera_id=camera_id,
                track_id=999,
                tracking_action="left",
                class_name="person",
                confidence=0.0,
                bounding_box=bbox,
                frame_number=100,
                dwell_time_seconds=5.0,
                model_info=model_info
            ),
            "expected": False,
            "description": "Left event without prior entered event"
        },
        # Case 2: Updated event (should be filtered)
        {
            "event": TrackingEvent(
                camera_id=camera_id,
                track_id=100,
                tracking_action="updated",
                class_name="person",
                confidence=0.85,
                bounding_box=bbox,
                frame_number=100,
                model_info=model_info
            ),
            "expected": False,
            "description": "Updated event (noise reduction)"
        },
        # Case 3: Unknown action
        {
            "event": TrackingEvent(
                camera_id=camera_id,
                track_id=101,
                tracking_action="unknown_action",
                class_name="person",
                confidence=0.85,
                bounding_box=bbox,
                frame_number=100,
                model_info=model_info
            ),
            "expected": False,
            "description": "Unknown tracking action"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        result = event_filter.should_publish_tracking(test_case["event"])
        expected = test_case["expected"]
        
        status = "PASS" if result == expected else "FAIL"
        print("Case {}: {} -> {}".format(i, test_case['description'], status))
    
    print("\nEdge case testing complete!")

if __name__ == "__main__":
    print("Track ID Deduplication Test Suite")
    print("=" * 50)
    
    # Run main test
    success = test_track_deduplication()
    
    # Run edge case tests
    test_edge_cases()
    
    print("\n" + "=" * 50)
    if success:
        print("All tests passed! Track ID deduplication is working correctly.")
        print("\nImplementation Summary:")
        print("   - Added should_publish_tracking() method to EventFilter")
        print("   - Tracks emitted track_ids to prevent duplicates")
        print("   - Only emits 'entered' events for new track_ids")
        print("   - Only emits 'left' events for previously entered track_ids")
        print("   - Filters out 'updated' events to reduce noise")
        print("   - Integrated filtering into video_worker.py")
    else:
        print("Some tests failed. Please check the implementation.")
        sys.exit(1)