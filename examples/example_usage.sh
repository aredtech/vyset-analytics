#!/bin/bash

# Example usage script for the Video Analytics Service

API_URL="http://localhost:8069"

echo "=== Video Analytics Service - Example Usage ==="
echo ""

# 1. Health Check
echo "1. Checking service health..."
curl -X GET "$API_URL/api/health" | jq .
echo ""
echo ""

# 2. Register a camera
echo "2. Registering a test camera..."
curl -X POST "$API_URL/api/cameras" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "camera_id": "cam-001",
      "status": "active",
      "stream_url": "rtsp://user:password@172.16.34.2:554/media/video1",
      "parameters": {
        "detection_classes": ["person", "car", "truck"],
        "confidence_threshold": 0.5,
        "enable_motion_detection": true,
        "enable_object_detection": true,
        "enable_anpr": false,
        "motion_threshold": 0.1,
        "frame_skip": 2,
        "max_fps": 15
      }
    }
  ]' | jq .
echo ""
echo ""

# 3. List all cameras
echo "3. Listing all cameras..."
curl -X GET "$API_URL/api/cameras" | jq .
echo ""
echo ""

# 4. Get specific camera
echo "4. Getting camera details..."
curl -X GET "$API_URL/api/cameras/cam-001" | jq .
echo ""
echo ""

# 5. Monitor Redis Pub/Sub (requires Python or redis-cli)
echo "5. Monitoring Redis events (press Ctrl+C to stop)..."
echo "Run this in a separate terminal:"
echo "python pubsub_consumer_example.py"
echo "# or use redis-cli:"
echo "docker exec -it redis redis-cli PSUBSCRIBE '*'"
echo ""

# Wait a bit
sleep 5

# 6. Delete camera
echo "6. Deleting camera..."
curl -X DELETE "$API_URL/api/cameras/cam-001" | jq .
echo ""
echo ""

echo "=== Example complete ==="

