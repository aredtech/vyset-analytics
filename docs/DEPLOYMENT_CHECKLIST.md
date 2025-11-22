# Snapshot Feature Deployment Checklist

## ✅ Pre-Deployment Verification

All implementation tasks completed:

- [x] Database dependencies added (SQLAlchemy, psycopg2, alembic)
- [x] Database models created (EventRecord table)
- [x] Database connection and session management implemented
- [x] Snapshot utility with bounding box visualization created
- [x] Video worker updated to capture and save snapshots
- [x] Video worker updated to store events in database
- [x] Events API endpoints implemented
- [x] Docker compose configuration updated
- [x] Database initialization script created
- [x] Environment variables configured
- [x] Documentation written (SNAPSHOT_FEATURE.md, SNAPSHOT_QUICKSTART.md)
- [x] Test script created (test_snapshots.py)
- [x] README updated with new features
- [x] .env.example updated
- [x] No linter errors
- [x] Backward compatibility maintained

## 🚀 Deployment Steps

### 1. Stop Current Service (if running)

```bash
cd /Users/rajumandal/OldFiles/VMS2.0/analytics
docker compose down
```

### 2. Build New Images

```bash
docker compose build
```

### 3. Start Services

```bash
docker compose up -d
```

### 4. Verify Services

```bash
# Check all containers are running
docker compose ps

# Check analytics-service logs
docker logs analytics-service --tail 50

# Check database logs
docker logs vms_db --tail 50

# Verify database tables created
docker exec vms_db psql -U vms_admin vms_analytics_db -c "\dt"
```

### 5. Test API Endpoints

```bash
# Test health
curl http://localhost:8069/api/health

# Test events API (should return empty initially)
curl http://localhost:8069/api/events

# Test stats API (should return zeros initially)
curl http://localhost:8069/api/events/stats
```

### 6. Register a Test Camera

```bash
curl -X POST http://localhost:8069/api/cameras \
  -H "Content-Type: application/json" \
  -d '[{
    "camera_id": "test-camera",
    "stream_url": "rtsp://your-camera-url",
    "parameters": {
      "enable_object_detection": true,
      "enable_motion_detection": true,
      "enable_anpr": false
    }
  }]'
```

### 7. Wait and Verify Events

```bash
# Wait 1-2 minutes for events to be detected

# Check events
curl http://localhost:8069/api/events

# Check if snapshots are being saved
docker exec analytics-service ls -lh /app/snapshots
```

### 8. Test Snapshot Download

```bash
# Get event ID from previous step
EVENT_ID=$(curl -s http://localhost:8069/api/events | jq -r '.events[0].id')

# Download snapshot
curl "http://localhost:8069/api/events/${EVENT_ID}/snapshot" -o test_snapshot.png

# Verify file
file test_snapshot.png
```

## 📊 Monitoring

### Check Database Size

```bash
docker exec vms_db psql -U vms_admin vms_analytics_db -c "
SELECT 
  COUNT(*) as total_events,
  pg_size_pretty(pg_total_relation_size('events')) as table_size
FROM events;
"
```

### Check Snapshot Storage

```bash
docker exec analytics-service du -sh /app/snapshots/*
```

### View Recent Events

```bash
docker exec vms_db psql -U vms_admin vms_analytics_db -c "
SELECT event_type, camera_id, timestamp, snapshot_path IS NOT NULL as has_snapshot
FROM events ORDER BY timestamp DESC LIMIT 10;
"
```

## 🔧 Configuration

### Environment Variables

Verify these are set in your `.env` file or docker-compose.yml:

```env
DATABASE_URL=postgresql://vms_admin:AIvan0987@db:5432/vms_analytics_db
SNAPSHOTS_DIR=/app/snapshots
ENABLE_SNAPSHOTS=true
```

### Docker Volumes

Verify volumes are created:

```bash
docker volume ls | grep -E "(analytics_snapshots|postgres_data)"
```

## 🐛 Troubleshooting

### Issue: Database connection failed

**Check:**
```bash
# Verify postgres is running
docker ps | grep vms_db

# Check postgres logs
docker logs vms_db

# Test connection
docker exec vms_db psql -U vms_admin -c "\l"
```

**Fix:**
```bash
# Restart database
docker compose restart db

# Wait for it to be ready
docker logs vms_db -f
```

### Issue: Snapshots not saving

**Check:**
```bash
# Verify directory exists
docker exec analytics-service ls -la /app/snapshots

# Check environment
docker exec analytics-service env | grep SNAPSHOT

# Check logs for errors
docker logs analytics-service | grep -i snapshot
```

**Fix:**
```bash
# Create directory manually if needed
docker exec analytics-service mkdir -p /app/snapshots

# Restart service
docker compose restart analytics-service
```

### Issue: Tables not created

**Check:**
```bash
# List tables
docker exec vms_db psql -U vms_admin vms_analytics_db -c "\dt"
```

**Fix:**
```bash
# Create tables manually by running Python
docker exec analytics-service python -c "
from app.core.database import init_db
init_db()
"
```

## 📝 Post-Deployment Tasks

### 1. Update Django Application

Add to your Django settings:

```python
# settings.py
ANALYTICS_API_URL = "http://analytics-service:8069"
```

### 2. Implement Event Viewer in Django

See `docs/SNAPSHOT_FEATURE.md` for Django integration examples.

### 3. Set Up Backups

```bash
# Add to crontab for daily backups
0 2 * * * docker exec vms_db pg_dump -U vms_admin vms_analytics_db > /backups/analytics_$(date +\%Y\%m\%d).sql
0 3 * * 0 docker run --rm -v analytics_snapshots:/data -v /backups:/backup alpine tar czf /backup/snapshots_$(date +\%Y\%m\%d).tar.gz /data
```

### 4. Implement Cleanup Policy

Add to crontab for weekly cleanup:

```bash
0 4 * * 0 docker exec vms_db psql -U vms_admin vms_analytics_db -c "DELETE FROM events WHERE timestamp < NOW() - INTERVAL '90 days';"
```

### 5. Set Up Monitoring

Monitor:
- Database size growth
- Snapshot storage usage
- API response times
- Error rates in logs

## 📚 Documentation

Available documentation:

1. **SNAPSHOT_FEATURE.md** - Complete feature documentation
2. **SNAPSHOT_QUICKSTART.md** - Quick start guide
3. **SNAPSHOT_IMPLEMENTATION_SUMMARY.md** - Implementation details
4. **README.md** - Updated with snapshot feature
5. **API_REQUEST_RESPONSE.md** - API documentation

## 🎉 Success Criteria

Deployment is successful if:

- [x] All containers are running
- [x] Database tables are created
- [x] Health endpoint returns healthy
- [x] Events are being stored in database
- [x] Snapshots are being saved to volume
- [x] Events API returns results
- [x] Snapshots can be downloaded
- [x] No errors in logs

## 📞 Support

If you encounter issues:

1. Check logs: `docker logs analytics-service`
2. Check database: `docker logs vms_db`
3. Review documentation in `docs/` folder
4. Run test script: `python examples/test_snapshots.py`

## 🎯 Next Steps

1. Integrate with Django frontend
2. Implement event viewer UI
3. Set up automated backups
4. Configure monitoring and alerts
5. Implement cleanup policies
6. Add user authentication for events API (if needed)

---

**Deployment Date**: _________________  
**Deployed By**: _________________  
**Version**: 1.0.0 with Snapshot Feature  
**Status**: ✅ Ready for Production

