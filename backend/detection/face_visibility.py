"""Conservative frontal-face evidence using OpenCV's locally bundled cascade.

No detected frontal face means unknown, not evidence of an uncovered face.
This is a visibility heuristic, not a trained head-pose or identity model.
"""
import threading

_cascade = None
_lock = threading.Lock()


def frontal_face_visible(frame, person_box):
    if frame is None:
        return False
    import cv2
    x1, y1, x2, y2 = map(int, person_box)
    height, width = frame.shape[:2]
    # Close-up crops may contain head and torso only; allow upper half.
    top, bottom = max(0, y1), min(height, int(y1 + (y2 - y1) * 0.5))
    left, right = max(0, x1), min(width, x2)
    if right - left < 24 or bottom - top < 24:
        return False
    head = cv2.cvtColor(frame[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
    global _cascade
    with _lock:
        if _cascade is None:
            _cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        if _cascade.empty():
            return False
        faces = _cascade.detectMultiScale(head, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
    # The face must be centered within this worker, not a neighboring face.
    return any(0.2 <= (fx + fw / 2) / (right - left) <= 0.8 for fx, fy, fw, fh in faces)
