# Django Integration Guide - Video Analytics Service

This document provides a comprehensive guide for integrating the Video Analytics Service with your Django-based Video Management System (VMS).

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Django Setup](#django-setup)
5. [Models](#models)
6. [API Integration](#api-integration)
7. [Redis Event Consumer](#redis-event-consumer)
8. [Views and Endpoints](#views-and-endpoints)
9. [Celery Configuration](#celery-configuration)
10. [Frontend Integration](#frontend-integration)
11. [Testing](#testing)
12. [Production Deployment](#production-deployment)

---

## Overview

The Video Analytics Service is a standalone FastAPI microservice that processes video streams in real-time and publishes events to Redis Streams. Your Django application will:

1. **Manage cameras** via REST API calls to the Analytics Service
2. **Consume events** from Redis Streams (detections, motion, ANPR)
3. **Store and process** events in your Django database
4. **Display** analytics results to users

### Key Features

- Real-time object detection (YOLOv8)
- Motion detection
- ANPR (License Plate Recognition)
- Multi-camera support
- Event-driven architecture via Redis Streams

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Django VMS Application                   │
│                                                                   │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │   Views/    │    │   Models     │    │  Event Consumer  │   │
│  │     API     │    │  (Database)  │    │  (Celery Task)   │   │
│  └──────┬──────┘    └──────▲───────┘    └────────▲─────────┘   │
│         │                   │                      │             │
└─────────┼───────────────────┼──────────────────────┼─────────────┘
          │                   │                      │
          │ HTTP              │ Store Events         │ Read Events
          │                   │                      │
          ▼                   │                      │
┌─────────────────────┐       │                      │
│  Analytics Service  │       │                      │
│    (FastAPI)        │       │                      │
│  - Object Detection │       │                      │
│  - Motion Detection │       │                      │
│  - ANPR             │       │                      │
└──────────┬──────────┘       │                      │
           │                  │                      │
           │ Publish Events   │                      │
           ▼                  │                      │
      ┌─────────┐             │                      │
      │  Redis  │─────────────┴──────────────────────┘
      │ Streams │
      └─────────┘
```

### Communication Flow

1. **Django → Analytics Service**: REST API calls to manage cameras
2. **Analytics Service → Redis**: Publishes detection/motion/ANPR events
3. **Redis → Django**: Celery task consumes events and stores in database
4. **Django → Frontend**: Displays events and analytics

---

## Prerequisites

### Required Services

- Django 4.2+ (or Django 3.2+)
- Redis 7.0+
- Celery 5.0+
- Python 3.11+
- Analytics Service (from this repository)

### Required Packages

Add to your `requirements.txt`:

```txt
# Django
Django>=4.2.0
djangorestframework>=3.14.0
django-cors-headers>=4.0.0

# Redis & Celery
redis>=5.0.0
celery>=5.3.0
django-celery-beat>=2.5.0

# HTTP Client
requests>=2.31.0
httpx>=0.24.0

# Additional utilities
python-decouple>=3.8
```

---

## Django Setup

### 1. Create Django App

```bash
python manage.py startapp video_analytics
```

### 2. Update Django Settings

Add to `settings.py`:

```python
# settings.py

INSTALLED_APPS = [
    # ... existing apps
    'rest_framework',
    'corsheaders',
    'video_analytics',
    'django_celery_beat',
]

# CORS Configuration (if needed)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Your frontend
]

# Analytics Service Configuration
ANALYTICS_SERVICE_URL = os.getenv('ANALYTICS_SERVICE_URL', 'http://localhost:8069')
ANALYTICS_SERVICE_TIMEOUT = 30  # seconds

# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_STREAM_NAME = os.getenv('REDIS_STREAM_NAME', 'stream:events')

# Celery Configuration
CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
```

### 3. Create `.env` File

```env
# .env
ANALYTICS_SERVICE_URL=http://analytics-service:8069
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_STREAM_NAME=stream:events
```

---

## Models

Create models to store events in `video_analytics/models.py`:

```python
# video_analytics/models.py

from django.db import models
from django.contrib.postgres.fields import JSONField  # or use models.JSONField for Django 3.1+
from django.utils import timezone


class Camera(models.Model):
    """Camera configuration model."""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
    ]
    
    camera_id = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    stream_url = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    
    # Processing parameters
    enable_object_detection = models.BooleanField(default=True)
    enable_motion_detection = models.BooleanField(default=True)
    enable_anpr = models.BooleanField(default=False)
    confidence_threshold = models.FloatField(default=0.5)
    detection_classes = models.JSONField(default=list)  # ["person", "car", "truck"]
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_active_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'cameras'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.camera_id})"


class DetectionEvent(models.Model):
    """Object detection event model."""
    
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='detections')
    timestamp = models.DateTimeField(db_index=True)
    frame_number = models.IntegerField()
    
    # Detection data
    detections = models.JSONField()  # List of detected objects
    detection_count = models.IntegerField(default=0)
    
    # Model info
    model_type = models.CharField(max_length=50)
    model_version = models.CharField(max_length=50)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'detection_events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['camera', 'timestamp']),
            models.Index(fields=['timestamp', 'processed']),
        ]
    
    def __str__(self):
        return f"Detection {self.camera.camera_id} @ {self.timestamp}"


class MotionEvent(models.Model):
    """Motion detection event model."""
    
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='motion_events')
    timestamp = models.DateTimeField(db_index=True)
    frame_number = models.IntegerField()
    
    # Motion data
    motion_intensity = models.FloatField()
    affected_area_percentage = models.FloatField()
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'motion_events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['camera', 'timestamp']),
            models.Index(fields=['timestamp', 'processed']),
        ]
    
    def __str__(self):
        return f"Motion {self.camera.camera_id} @ {self.timestamp}"


class ANPREvent(models.Model):
    """ANPR (License Plate Recognition) event model."""
    
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='anpr_events')
    timestamp = models.DateTimeField(db_index=True)
    frame_number = models.IntegerField()
    
    # ANPR data
    license_plate = models.CharField(max_length=20, db_index=True)
    confidence = models.FloatField()
    region = models.CharField(max_length=50, blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'anpr_events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['camera', 'timestamp']),
            models.Index(fields=['license_plate']),
            models.Index(fields=['timestamp', 'processed']),
        ]
    
    def __str__(self):
        return f"ANPR {self.license_plate} @ {self.timestamp}"


class EventStatistics(models.Model):
    """Aggregated statistics for cameras."""
    
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='statistics')
    date = models.DateField(db_index=True)
    
    # Counts
    detection_count = models.IntegerField(default=0)
    motion_count = models.IntegerField(default=0)
    anpr_count = models.IntegerField(default=0)
    
    # Object detection breakdown
    person_count = models.IntegerField(default=0)
    car_count = models.IntegerField(default=0)
    truck_count = models.IntegerField(default=0)
    other_count = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'event_statistics'
        unique_together = ['camera', 'date']
        ordering = ['-date']
    
    def __str__(self):
        return f"Stats {self.camera.camera_id} - {self.date}"
```

### Run Migrations

```bash
python manage.py makemigrations video_analytics
python manage.py migrate video_analytics
```

---

## API Integration

Create a service class to interact with the Analytics Service:

```python
# video_analytics/services/analytics_client.py

import requests
import logging
from django.conf import settings
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class AnalyticsServiceClient:
    """Client for interacting with the Analytics Service API."""
    
    def __init__(self):
        self.base_url = settings.ANALYTICS_SERVICE_URL
        self.timeout = settings.ANALYTICS_SERVICE_TIMEOUT
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
        })
    
    def health_check(self) -> Dict:
        """Check health of analytics service."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/health",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Analytics service health check failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def register_camera(self, camera_data: Dict) -> Dict:
        """
        Register a camera with the analytics service.
        
        Args:
            camera_data: Camera configuration dictionary
            
        Returns:
            Response from analytics service
        """
        try:
            payload = [camera_data]  # API expects a list
            response = self.session.post(
                f"{self.base_url}/api/cameras",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to register camera: {e}")
            raise
    
    def list_cameras(self) -> List[Dict]:
        """Get list of all cameras from analytics service."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/cameras",
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data.get('cameras', [])
        except Exception as e:
            logger.error(f"Failed to list cameras: {e}")
            return []
    
    def get_camera(self, camera_id: str) -> Optional[Dict]:
        """Get specific camera configuration."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/cameras/{camera_id}",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get camera {camera_id}: {e}")
            return None
    
    def delete_camera(self, camera_id: str) -> bool:
        """Stop and remove a camera from analytics service."""
        try:
            response = self.session.delete(
                f"{self.base_url}/api/cameras/{camera_id}",
                timeout=self.timeout
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to delete camera {camera_id}: {e}")
            return False
    
    def build_camera_config(self, camera) -> Dict:
        """
        Build camera configuration for analytics service.
        
        Args:
            camera: Django Camera model instance
            
        Returns:
            Dictionary with camera configuration
        """
        return {
            "camera_id": camera.camera_id,
            "status": camera.status,
            "stream_url": camera.stream_url,
            "parameters": {
                "detection_classes": camera.detection_classes or ["person", "car", "truck"],
                "confidence_threshold": camera.confidence_threshold,
                "roi_zones": [],
                "enable_motion_detection": camera.enable_motion_detection,
                "enable_object_detection": camera.enable_object_detection,
                "enable_anpr": camera.enable_anpr,
                "motion_threshold": 0.1,
                "frame_skip": 1,
                "max_fps": 30
            }
        }


# Create a singleton instance
analytics_client = AnalyticsServiceClient()
```

---

## Redis Event Consumer

Create a Celery task to consume events from Redis Streams:

```python
# video_analytics/tasks.py

import json
import logging
import redis
from datetime import datetime
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from .models import Camera, DetectionEvent, MotionEvent, ANPREvent, EventStatistics

logger = logging.getLogger(__name__)


class RedisEventConsumer:
    """Consumer for Redis Stream events."""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.stream_name = settings.REDIS_STREAM_NAME
        self.last_id = '0'  # Start from beginning, or use '$' for new messages only
    
    def consume_events(self, count=100, block_ms=1000):
        """
        Consume events from Redis Stream.
        
        Args:
            count: Maximum number of messages to read
            block_ms: Milliseconds to block waiting for messages
            
        Returns:
            Number of events processed
        """
        try:
            messages = self.redis_client.xread(
                {self.stream_name: self.last_id},
                count=count,
                block=block_ms
            )
            
            events_processed = 0
            
            for stream, events in messages:
                for event_id, data in events:
                    self.last_id = event_id
                    
                    try:
                        event_json = data.get('data', '{}')
                        event = json.loads(event_json)
                        self.process_event(event)
                        events_processed += 1
                    except Exception as e:
                        logger.error(f"Error processing event {event_id}: {e}")
            
            return events_processed
            
        except Exception as e:
            logger.error(f"Error consuming from Redis Stream: {e}")
            return 0
    
    def process_event(self, event: dict):
        """
        Process a single event and store in database.
        
        Args:
            event: Event dictionary
        """
        event_type = event.get('event_type')
        camera_id = event.get('camera_id')
        
        try:
            camera = Camera.objects.get(camera_id=camera_id)
            
            # Update camera last_active_at
            camera.last_active_at = timezone.now()
            camera.save(update_fields=['last_active_at'])
            
            # Route to appropriate handler
            if event_type == 'detection':
                self._process_detection_event(camera, event)
            elif event_type == 'motion':
                self._process_motion_event(camera, event)
            elif event_type == 'anpr':
                self._process_anpr_event(camera, event)
            else:
                logger.warning(f"Unknown event type: {event_type}")
                
        except Camera.DoesNotExist:
            logger.warning(f"Camera not found: {camera_id}")
        except Exception as e:
            logger.error(f"Error processing {event_type} event: {e}")
    
    def _process_detection_event(self, camera: Camera, event: dict):
        """Process object detection event."""
        timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
        
        with transaction.atomic():
            # Create detection event
            detection = DetectionEvent.objects.create(
                camera=camera,
                timestamp=timestamp,
                frame_number=event['frame_number'],
                detections=event['detections'],
                detection_count=len(event['detections']),
                model_type=event['model_info']['model_type'],
                model_version=event['model_info']['version']
            )
            
            # Update statistics
            self._update_statistics(camera, timestamp, event_type='detection', event_data=event)
        
        logger.info(f"Stored detection event: {detection.id}")
    
    def _process_motion_event(self, camera: Camera, event: dict):
        """Process motion detection event."""
        timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
        
        with transaction.atomic():
            # Create motion event
            motion = MotionEvent.objects.create(
                camera=camera,
                timestamp=timestamp,
                frame_number=event['frame_number'],
                motion_intensity=event['motion_intensity'],
                affected_area_percentage=event['affected_area_percentage']
            )
            
            # Update statistics
            self._update_statistics(camera, timestamp, event_type='motion')
        
        logger.debug(f"Stored motion event: {motion.id}")
    
    def _process_anpr_event(self, camera: Camera, event: dict):
        """Process ANPR event."""
        timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
        anpr_result = event['anpr_result']
        
        with transaction.atomic():
            # Create ANPR event
            anpr = ANPREvent.objects.create(
                camera=camera,
                timestamp=timestamp,
                frame_number=event['frame_number'],
                license_plate=anpr_result['license_plate'],
                confidence=anpr_result['confidence'],
                region=anpr_result.get('region')
            )
            
            # Update statistics
            self._update_statistics(camera, timestamp, event_type='anpr')
        
        logger.info(f"Stored ANPR event: {anpr.id} - {anpr.license_plate}")
    
    def _update_statistics(self, camera: Camera, timestamp, event_type: str, event_data: dict = None):
        """Update daily statistics."""
        date = timestamp.date()
        
        stats, created = EventStatistics.objects.get_or_create(
            camera=camera,
            date=date
        )
        
        if event_type == 'detection':
            stats.detection_count += 1
            
            # Update object counts
            if event_data:
                for detection in event_data.get('detections', []):
                    class_name = detection['class_name']
                    if class_name == 'person':
                        stats.person_count += 1
                    elif class_name == 'car':
                        stats.car_count += 1
                    elif class_name == 'truck':
                        stats.truck_count += 1
                    else:
                        stats.other_count += 1
        
        elif event_type == 'motion':
            stats.motion_count += 1
        
        elif event_type == 'anpr':
            stats.anpr_count += 1
        
        stats.save()


@shared_task(name='video_analytics.consume_redis_events')
def consume_redis_events():
    """Celery task to consume Redis events."""
    consumer = RedisEventConsumer()
    events_processed = consumer.consume_events(count=100, block_ms=1000)
    
    if events_processed > 0:
        logger.info(f"Processed {events_processed} events")
    
    return events_processed


@shared_task(name='video_analytics.continuous_event_consumer')
def continuous_event_consumer():
    """
    Continuous consumer task (run this as a long-running task).
    This should be started manually and kept running.
    """
    consumer = RedisEventConsumer()
    logger.info("Starting continuous event consumer...")
    
    try:
        while True:
            consumer.consume_events(count=100, block_ms=5000)
    except KeyboardInterrupt:
        logger.info("Stopping continuous event consumer...")
```

---

## Views and Endpoints

Create Django REST Framework views:

```python
# video_analytics/serializers.py

from rest_framework import serializers
from .models import Camera, DetectionEvent, MotionEvent, ANPREvent, EventStatistics


class CameraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Camera
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'last_active_at']


class DetectionEventSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    
    class Meta:
        model = DetectionEvent
        fields = '__all__'


class MotionEventSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    
    class Meta:
        model = MotionEvent
        fields = '__all__'


class ANPREventSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    
    class Meta:
        model = ANPREvent
        fields = '__all__'


class EventStatisticsSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    
    class Meta:
        model = EventStatistics
        fields = '__all__'
```

```python
# video_analytics/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from .models import Camera, DetectionEvent, MotionEvent, ANPREvent, EventStatistics
from .serializers import (
    CameraSerializer, DetectionEventSerializer, MotionEventSerializer,
    ANPREventSerializer, EventStatisticsSerializer
)
from .services.analytics_client import analytics_client


class CameraViewSet(viewsets.ModelViewSet):
    """ViewSet for managing cameras."""
    
    queryset = Camera.objects.all()
    serializer_class = CameraSerializer
    lookup_field = 'camera_id'
    
    def create(self, request, *args, **kwargs):
        """Create camera in Django and register with analytics service."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Save to Django database
        camera = serializer.save()
        
        # Register with analytics service
        try:
            camera_config = analytics_client.build_camera_config(camera)
            result = analytics_client.register_camera(camera_config)
            
            camera.status = 'active'
            camera.save()
            
            return Response({
                'camera': serializer.data,
                'analytics_result': result
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            camera.status = 'error'
            camera.save()
            return Response({
                'camera': serializer.data,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def destroy(self, request, *args, **kwargs):
        """Delete camera from Django and analytics service."""
        camera = self.get_object()
        camera_id = camera.camera_id
        
        # Remove from analytics service
        analytics_client.delete_camera(camera_id)
        
        # Delete from Django database
        self.perform_destroy(camera)
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'])
    def start(self, request, camera_id=None):
        """Start camera processing."""
        camera = self.get_object()
        
        try:
            camera_config = analytics_client.build_camera_config(camera)
            result = analytics_client.register_camera(camera_config)
            
            camera.status = 'active'
            camera.save()
            
            return Response({'status': 'started', 'result': result})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def stop(self, request, camera_id=None):
        """Stop camera processing."""
        camera = self.get_object()
        
        analytics_client.delete_camera(camera.camera_id)
        camera.status = 'inactive'
        camera.save()
        
        return Response({'status': 'stopped'})
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, camera_id=None):
        """Get camera statistics."""
        camera = self.get_object()
        days = int(request.query_params.get('days', 7))
        
        start_date = timezone.now().date() - timedelta(days=days)
        stats = EventStatistics.objects.filter(
            camera=camera,
            date__gte=start_date
        ).order_by('-date')
        
        serializer = EventStatisticsSerializer(stats, many=True)
        return Response(serializer.data)


class DetectionEventViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for detection events."""
    
    queryset = DetectionEvent.objects.select_related('camera').all()
    serializer_class = DetectionEventSerializer
    filterset_fields = ['camera__camera_id', 'processed']
    ordering_fields = ['timestamp', 'created_at']
    
    def get_queryset(self):
        """Filter by date range if provided."""
        queryset = super().get_queryset()
        
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        return queryset


class MotionEventViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for motion events."""
    
    queryset = MotionEvent.objects.select_related('camera').all()
    serializer_class = MotionEventSerializer
    filterset_fields = ['camera__camera_id', 'processed']
    ordering_fields = ['timestamp', 'created_at']


class ANPREventViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for ANPR events."""
    
    queryset = ANPREvent.objects.select_related('camera').all()
    serializer_class = ANPREventSerializer
    filterset_fields = ['camera__camera_id', 'license_plate', 'processed']
    ordering_fields = ['timestamp', 'created_at']
```

### URL Configuration

```python
# video_analytics/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CameraViewSet, DetectionEventViewSet, MotionEventViewSet, ANPREventViewSet

router = DefaultRouter()
router.register(r'cameras', CameraViewSet, basename='camera')
router.register(r'detections', DetectionEventViewSet, basename='detection')
router.register(r'motion', MotionEventViewSet, basename='motion')
router.register(r'anpr', ANPREventViewSet, basename='anpr')

urlpatterns = [
    path('', include(router.urls)),
]
```

```python
# project/urls.py (main urls.py)

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/analytics/', include('video_analytics.urls')),
    # ... other paths
]
```

---

## Celery Configuration

### 1. Create Celery App

```python
# project/celery.py

import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

app = Celery('project')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks
app.autodiscover_tasks()

# Periodic tasks
app.conf.beat_schedule = {
    'consume-redis-events': {
        'task': 'video_analytics.consume_redis_events',
        'schedule': 5.0,  # Every 5 seconds
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
```

```python
# project/__init__.py

from .celery import app as celery_app

__all__ = ('celery_app',)
```

### 2. Start Celery Workers

```bash
# Terminal 1: Start Celery worker
celery -A project worker --loglevel=info

# Terminal 2: Start Celery beat (for periodic tasks)
celery -A project beat --loglevel=info

# Or run both together
celery -A project worker --beat --loglevel=info
```

---

## Frontend Integration

### Example API Calls (JavaScript/React)

```javascript
// api/analytics.js

const API_BASE_URL = 'http://localhost:8000/api/v1/analytics';

// Get all cameras
export const getCameras = async () => {
  const response = await fetch(`${API_BASE_URL}/cameras/`);
  return response.json();
};

// Create a camera
export const createCamera = async (cameraData) => {
  const response = await fetch(`${API_BASE_URL}/cameras/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(cameraData),
  });
  return response.json();
};

// Start camera processing
export const startCamera = async (cameraId) => {
  const response = await fetch(`${API_BASE_URL}/cameras/${cameraId}/start/`, {
    method: 'POST',
  });
  return response.json();
};

// Stop camera processing
export const stopCamera = async (cameraId) => {
  const response = await fetch(`${API_BASE_URL}/cameras/${cameraId}/stop/`, {
    method: 'POST',
  });
  return response.json();
};

// Get detection events
export const getDetections = async (cameraId, startDate, endDate) => {
  const params = new URLSearchParams({
    camera__camera_id: cameraId,
    start_date: startDate,
    end_date: endDate,
  });
  
  const response = await fetch(`${API_BASE_URL}/detections/?${params}`);
  return response.json();
};

// Get camera statistics
export const getCameraStatistics = async (cameraId, days = 7) => {
  const response = await fetch(
    `${API_BASE_URL}/cameras/${cameraId}/statistics/?days=${days}`
  );
  return response.json();
};
```

---

## Testing

### Unit Tests

```python
# video_analytics/tests/test_models.py

from django.test import TestCase
from django.utils import timezone
from video_analytics.models import Camera, DetectionEvent


class CameraModelTest(TestCase):
    def setUp(self):
        self.camera = Camera.objects.create(
            camera_id='test-cam-001',
            name='Test Camera',
            stream_url='rtsp://test',
            status='active'
        )
    
    def test_camera_creation(self):
        self.assertEqual(self.camera.camera_id, 'test-cam-001')
        self.assertEqual(self.camera.status, 'active')
    
    def test_camera_str(self):
        self.assertEqual(str(self.camera), 'Test Camera (test-cam-001)')


class DetectionEventModelTest(TestCase):
    def setUp(self):
        self.camera = Camera.objects.create(
            camera_id='test-cam-001',
            name='Test Camera',
            stream_url='rtsp://test'
        )
        
        self.detection = DetectionEvent.objects.create(
            camera=self.camera,
            timestamp=timezone.now(),
            frame_number=100,
            detections=[
                {
                    'class_name': 'person',
                    'confidence': 0.95,
                    'bounding_box': {'x': 0.1, 'y': 0.2, 'width': 0.3, 'height': 0.4}
                }
            ],
            detection_count=1,
            model_type='yolov8n',
            model_version='8.1.0'
        )
    
    def test_detection_creation(self):
        self.assertEqual(self.detection.camera, self.camera)
        self.assertEqual(self.detection.detection_count, 1)
```

### Integration Tests

```python
# video_analytics/tests/test_views.py

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from video_analytics.models import Camera


class CameraAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.camera_data = {
            'camera_id': 'test-cam-001',
            'name': 'Test Camera',
            'stream_url': 'rtsp://test',
            'status': 'inactive'
        }
    
    def test_create_camera(self):
        response = self.client.post(
            '/api/v1/analytics/cameras/',
            self.camera_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_list_cameras(self):
        Camera.objects.create(**self.camera_data)
        response = self.client.get('/api/v1/analytics/cameras/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)
```

### Run Tests

```bash
python manage.py test video_analytics
```

---

## Production Deployment

### Docker Compose Setup

Create a `docker-compose.yml` for the complete stack:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - vms_network
  
  analytics-service:
    build: ./analytics
    container_name: analytics-service
    ports:
      - "8069:8069"
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - YOLO_MODEL=yolov8n.pt
    depends_on:
      - redis
    networks:
      - vms_network
  
  django-db:
    image: postgres:15-alpine
    container_name: django-db
    environment:
      - POSTGRES_DB=vms_db
      - POSTGRES_USER=vms_user
      - POSTGRES_PASSWORD=your_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - vms_network
  
  django-app:
    build: ./django
    container_name: django-app
    command: gunicorn project.wsgi:application --bind 0.0.0.0:8000
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://vms_user:your_password@django-db:5432/vms_db
      - REDIS_HOST=redis
      - ANALYTICS_SERVICE_URL=http://analytics-service:8069
    depends_on:
      - django-db
      - redis
      - analytics-service
    networks:
      - vms_network
  
  celery-worker:
    build: ./django
    container_name: celery-worker
    command: celery -A project worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://vms_user:your_password@django-db:5432/vms_db
      - REDIS_HOST=redis
    depends_on:
      - django-db
      - redis
    networks:
      - vms_network
  
  celery-beat:
    build: ./django
    container_name: celery-beat
    command: celery -A project beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://vms_user:your_password@django-db:5432/vms_db
      - REDIS_HOST=redis
    depends_on:
      - django-db
      - redis
    networks:
      - vms_network

networks:
  vms_network:
    driver: bridge

volumes:
  redis_data:
  postgres_data:
```

### Environment Variables

Create `.env` file:

```env
# Django
DEBUG=False
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

# Database
DATABASE_URL=postgresql://vms_user:your_password@django-db:5432/vms_db

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_STREAM_NAME=stream:events

# Analytics Service
ANALYTICS_SERVICE_URL=http://analytics-service:8069
ANALYTICS_SERVICE_TIMEOUT=30
```

### Start Complete Stack

```bash
docker-compose up --build -d
```

---

## Best Practices

### 1. Error Handling

- Always handle connection errors to the Analytics Service
- Implement retry logic for failed API calls
- Log all errors for debugging

### 2. Performance Optimization

- Use database indexes on frequently queried fields
- Implement pagination for large datasets
- Use select_related() and prefetch_related() for query optimization
- Consider implementing data retention policies

### 3. Security

- Use authentication/authorization for API endpoints
- Validate all input data
- Use HTTPS in production
- Secure Redis with password authentication
- Use environment variables for sensitive data

### 4. Monitoring

- Monitor Celery task queue length
- Track Redis Stream size
- Set up alerts for service failures
- Log all critical operations

### 5. Scalability

- Run multiple Celery workers for event processing
- Use database connection pooling
- Implement caching for frequently accessed data
- Consider partitioning large tables by date

---

## Troubleshooting

### Issue: Events not appearing in Django

**Solution:**
1. Check if Celery worker is running: `celery -A project inspect active`
2. Verify Redis connection: `python manage.py shell` → `from django.conf import settings; import redis; r = redis.Redis(host=settings.REDIS_HOST)`
3. Check Analytics Service is publishing events
4. Review Celery logs for errors

### Issue: Camera registration fails

**Solution:**
1. Verify Analytics Service is running: `curl http://localhost:8069/api/health`
2. Check stream URL is accessible
3. Review Analytics Service logs
4. Verify network connectivity between services

### Issue: High database load

**Solution:**
1. Implement batch inserts for events
2. Add database indexes
3. Use database connection pooling
4. Consider archiving old events

---

## Support

For issues and questions:
- Check the logs: `docker-compose logs -f`
- Review the README.md in the analytics service
- Open an issue on the repository

---

## License

MIT License

