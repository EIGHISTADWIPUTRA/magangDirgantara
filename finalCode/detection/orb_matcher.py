"""ORB feature matching module.

Provides a class-based interface for ORB feature detection and FLANN-based
matching against multiple target images.
"""

import cv2
import numpy as np
import os
from typing import Optional

from finalCode.config import (
    ORB_NFEATURES,
    ORB_RATIO_THRESHOLD,
    MIN_GOOD_MATCHES,
    MAX_DRAW_MATCHES,
    FLANN_ALGORITHM_LSH,
    FLANN_TABLE_NUMBER,
    FLANN_KEY_SIZE,
    FLANN_MULTI_PROBE_LEVEL,
    FLANN_CHECKS,
    SUPPORTED_IMAGE_EXTENSIONS,
)


class ORBMatcher:
    """ORB feature detector with FLANN-based matching.
    
    Uses ORB (Oriented FAST and Rotated BRIEF) for keypoint detection
    and FLANN with LSH algorithm for efficient binary descriptor matching.
    
    Attributes:
        detector: OpenCV ORB detector instance.
        flann: FLANN-based matcher configured for binary descriptors.
        targets: List of loaded target images with extracted features.
        ratio_threshold: Lowe's ratio test threshold.
    
    Example:
        >>> matcher = ORBMatcher()
        >>> matcher.load_targets('received_images/')
        >>> match_info = matcher.match_frame(frame)
        >>> if match_info and match_info['count'] >= 10:
        ...     print(f"Detected: {match_info['name']}")
    """
    
    def __init__(self, nfeatures: int = ORB_NFEATURES,
                 ratio_threshold: float = ORB_RATIO_THRESHOLD):
        """Initialize ORB detector and FLANN matcher.
        
        Args:
            nfeatures: Maximum number of features to retain. Default from config.
            ratio_threshold: Lowe's ratio test threshold (0-1). Default from config.
        """
        # Create ORB detector
        self.detector = cv2.ORB_create(nfeatures=nfeatures)
        
        # FLANN parameters for binary descriptors (ORB) using LSH algorithm
        index_params = dict(
            algorithm=FLANN_ALGORITHM_LSH,
            table_number=FLANN_TABLE_NUMBER,
            key_size=FLANN_KEY_SIZE,
            multi_probe_level=FLANN_MULTI_PROBE_LEVEL,
        )
        search_params = dict(checks=FLANN_CHECKS)
        
        self.flann = cv2.FlannBasedMatcher(index_params, search_params)
        self.targets = []
        self.ratio_threshold = ratio_threshold
        
        print(f"[V] ORBMatcher initialized (nfeatures={nfeatures}, ratio={ratio_threshold})")
    
    def load_targets(self, folder: str) -> int:
        """Load all target images from a folder and extract keypoints/descriptors.
        
        Args:
            folder: Path to folder containing target images.
        
        Returns:
            Number of successfully loaded targets.
        """
        self.targets = []
        
        if not os.path.exists(folder):
            print(f"[x] Folder '{folder}' not found")
            return 0
        
        print(f"[*] Loading target images from {folder}/ ...")
        
        for filename in sorted(os.listdir(folder)):
            if not filename.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS):
                continue
            
            filepath = os.path.join(folder, filename)
            img = cv2.imread(filepath)
            
            if img is None:
                print(f"    [!] Failed to load: {filename}")
                continue
            
            # Convert to grayscale and extract features
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            keypoints, descriptors = self.detector.detectAndCompute(gray, None)
            
            if descriptors is None or len(keypoints) == 0:
                print(f"    [!] No keypoints in {filename}, skipped")
                continue
            
            self.targets.append({
                'name': filename,
                'image': img,
                'keypoints': keypoints,
                'descriptors': descriptors,
                'path': filepath,
            })
            print(f"    [V] {filename} - {len(keypoints)} keypoints")
        
        print(f"    Total: {len(self.targets)} targets loaded")
        return len(self.targets)
    
    def match_frame(self, frame) -> Optional[dict]:
        """Match frame against all loaded targets, return best match.
        
        Args:
            frame: Input frame as numpy array (BGR format).
        
        Returns:
            Dictionary with match info for best target, or None if no match.
            Keys: 'name', 'good_matches', 'count', 'image', 'keypoints',
                  'frame_keypoints', 'frame_descriptors'
        """
        if not self.targets:
            return None
        
        # Convert frame to grayscale and extract features
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kp_frame, desc_frame = self.detector.detectAndCompute(gray_frame, None)
        
        if desc_frame is None or len(kp_frame) == 0:
            return None
        
        best_match = None
        max_matches = 0
        
        for target in self.targets:
            try:
                # Perform kNN matching
                raw_matches = self.flann.knnMatch(target['descriptors'], desc_frame, k=2)
                
                # Apply Lowe's ratio test
                good_matches = []
                for pair in raw_matches:
                    if len(pair) == 2:
                        m, n = pair
                        if m.distance < self.ratio_threshold * n.distance:
                            good_matches.append(m)
                
                if len(good_matches) > max_matches:
                    max_matches = len(good_matches)
                    best_match = {
                        'name': target['name'],
                        'good_matches': good_matches,
                        'count': len(good_matches),
                        'image': target['image'],
                        'keypoints': target['keypoints'],
                        'frame_keypoints': kp_frame,
                        'frame_descriptors': desc_frame,
                    }
                    
            except Exception as e:
                print(f"[!] Error matching against {target['name']}: {e}")
                continue
        
        return best_match
    
    def match_single(self, frame, target: dict) -> dict:
        """Match frame against a single target.
        
        Args:
            frame: Input frame as numpy array (BGR format).
            target: Target dictionary from self.targets list.
        
        Returns:
            Dictionary with match info.
            Keys: 'name', 'good_matches', 'count', 'image', 'keypoints',
                  'frame_keypoints', 'frame_descriptors'
        """
        # Convert frame to grayscale and extract features
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kp_frame, desc_frame = self.detector.detectAndCompute(gray_frame, None)
        
        result = {
            'name': target['name'],
            'good_matches': [],
            'count': 0,
            'image': target['image'],
            'keypoints': target['keypoints'],
            'frame_keypoints': kp_frame,
            'frame_descriptors': desc_frame,
        }
        
        if desc_frame is None or len(kp_frame) == 0:
            return result
        
        try:
            # Perform kNN matching
            raw_matches = self.flann.knnMatch(target['descriptors'], desc_frame, k=2)
            
            # Apply Lowe's ratio test
            good_matches = []
            for pair in raw_matches:
                if len(pair) == 2:
                    m, n = pair
                    if m.distance < self.ratio_threshold * n.distance:
                        good_matches.append(m)
            
            result['good_matches'] = good_matches
            result['count'] = len(good_matches)
            
        except Exception as e:
            print(f"[!] Error matching against {target['name']}: {e}")
        
        return result
    
    def draw_matches(self, frame, kp_frame, match_info: dict,
                     fps: float = 0.0, max_matches: int = MAX_DRAW_MATCHES) -> Optional[np.ndarray]:
        """Draw match visualization (side-by-side with info overlay).
        
        Args:
            frame: Input frame as numpy array (BGR format).
            kp_frame: Keypoints detected in frame.
            match_info: Match result dictionary from match_frame() or match_single().
            fps: Current FPS value to display. Default 0.0.
            max_matches: Maximum number of match lines to draw. Default from config.
        
        Returns:
            Visualization image with matches drawn, or None on error.
        """
        if match_info is None:
            return None
        
        target_img = match_info['image']
        target_kp = match_info['keypoints']
        good_matches = match_info['good_matches'][:max_matches]
        match_count = match_info['count']
        target_name = match_info['name']
        is_detected = match_count >= MIN_GOOD_MATCHES
        
        try:
            # Draw matches side-by-side
            viz = cv2.drawMatches(
                target_img, target_kp,
                frame, kp_frame,
                good_matches, None,
                flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
            )
            
            # Overlay status info
            status = "DETECTED!" if is_detected else f"Matches: {match_count}"
            status_color = (0, 255, 0) if is_detected else (0, 200, 255)
            
            # Title + Status (top-left)
            cv2.putText(viz, f"[ORB] {target_name}  |  {status}",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            
            # FPS (top-right)
            width = viz.shape[1]
            cv2.putText(viz, f"FPS: {int(fps)}", (width - 130, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            
            # Threshold info (bottom-left)
            cv2.putText(viz, f"Min threshold: {MIN_GOOD_MATCHES}",
                        (10, viz.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
            
            return viz
            
        except Exception as e:
            print(f"[!] Error creating match visualization: {e}")
            return None
    
    def get_target_by_index(self, index: int) -> Optional[dict]:
        """Get target by index with bounds checking.
        
        Args:
            index: Target index (wraps around with modulo).
        
        Returns:
            Target dictionary or None if no targets loaded.
        """
        if not self.targets:
            return None
        return self.targets[index % len(self.targets)]
    
    def get_target_count(self) -> int:
        """Get number of loaded targets.
        
        Returns:
            Number of targets currently loaded.
        """
        return len(self.targets)
