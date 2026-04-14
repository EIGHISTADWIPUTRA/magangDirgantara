"""Webcam streaming module.

Provides a clean interface for capturing frames from a webcam with
automatic resource management via context manager support.
"""

import cv2
import time

from finalCode.config import CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT


class WebcamStream:
    """Thread-safe webcam capture with configurable resolution.
    
    Attributes:
        stream: OpenCV VideoCapture instance.
    
    Example:
        >>> with WebcamStream() as cam:
        ...     ret, frame = cam.get_frame()
        ...     if ret:
        ...         cv2.imshow('Frame', frame)
    """
    
    def __init__(self, source=CAMERA_INDEX, width=CAMERA_WIDTH, height=CAMERA_HEIGHT):
        """Initialize webcam stream.
        
        Args:
            source: Camera index (int) or video file path (str). Defaults to config value.
            width: Frame width in pixels. Defaults to config value.
            height: Frame height in pixels. Defaults to config value.
        
        Raises:
            ValueError: If source is not int or str.
            RuntimeError: If camera cannot be opened.
        """
        # Validate source parameter
        if not isinstance(source, (int, str)):
            raise ValueError(f"[x] Camera source must be int or str, got {type(source)}")
        
        try:
            # Initialize camera
            self.stream = cv2.VideoCapture(source, cv2.CAP_V4L2)
            
            # Set frame dimensions
            self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            time.sleep(1)
            # Verify camera is opened
            if not self.stream.isOpened():
                print("[x] No camera found")
                raise RuntimeError(f"Failed to open camera from source: {source}")
                
        except cv2.error as e:
            print(f"[x] OpenCV error during camera initialization: {e}")
            raise
        except Exception as e:
            print(f"[x] Unexpected error during camera initialization: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if camera is ready for capture.
        
        Returns:
            True if camera is opened and ready, False otherwise.
        """
        return self.stream.isOpened()
    
    # Keep Indonesian method name for backward compatibility
    siap = is_ready
    
    def get_frame(self):
        """Capture the latest frame from camera.
        
        Returns:
            Tuple of (success: bool, frame: numpy.ndarray).
            success is True if frame was captured successfully.
            frame contains pixel data as numpy array (BGR format).
        """
        ret, frame = self.stream.read()
        return ret, frame
    
    def stop(self):
        """Release camera resources."""
        try:
            if self.stream is not None:
                self.stream.release()
        except Exception as e:
            print(f"[!] Warning: Error closing camera - {e}")
    
    # Keep Indonesian method name for backward compatibility
    berhenti = stop
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic resource cleanup."""
        self.stop()
        return False  # Don't suppress exceptions
