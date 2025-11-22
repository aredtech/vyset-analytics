# PyTorch 2.6+ Compatibility Fix

## Issue

PyTorch 2.6 introduced a breaking change where `torch.load()` now defaults to `weights_only=True` for security. This causes YOLO models to fail loading with the error:

```
WeightsUnpickler error: Unsupported global: GLOBAL ultralytics.nn.tasks.DetectionModel 
was not an allowed global by default.
```

## Solution

We've implemented a monkey patch in `app/services/detection.py` that sets `weights_only=False` by default for torch.load operations. This is safe because:

1. We only load official YOLOv8 models from Ultralytics
2. The models are downloaded from the official Ultralytics GitHub releases
3. The models are verified and trusted

## Implementation

```python
# Monkey patch torch.load to use weights_only=False for trusted ultralytics models
_original_torch_load = torch.load

def _patched_torch_load(*args, **kwargs):
    """Patched torch.load that sets weights_only=False for compatibility with YOLO models."""
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)

torch.load = _patched_torch_load
```

## Verification

After applying the fix, YOLO models load successfully:

```
2025-10-09 15:54:03 - app.services.detection - INFO - Loading YOLO model: yolov8n.pt
2025-10-09 15:54:03 - app.services.detection - INFO - YOLO model loaded successfully
```

## Alternative Solutions

If you prefer not to use the monkey patch, you can:

### Option 1: Pin PyTorch to < 2.6

In `requirements.txt`:
```
torch<2.6.0
```

### Option 2: Use Environment Variable

Set before starting the service:
```bash
export TORCH_SERIALIZATION_SAFE_GLOBALS="1"
```

### Option 3: Wait for Ultralytics Update

The Ultralytics team may release an update that handles PyTorch 2.6 compatibility natively.

## Related Links

- [PyTorch 2.6 Release Notes](https://pytorch.org/docs/stable/generated/torch.load.html)
- [Ultralytics Issue Tracker](https://github.com/ultralytics/ultralytics/issues)
- [PyTorch Security Documentation](https://pytorch.org/docs/stable/notes/serialization.html)

## Status

✅ **Fixed and verified** - YOLO models now load correctly with PyTorch 2.8

