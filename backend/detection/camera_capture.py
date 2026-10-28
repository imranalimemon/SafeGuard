"""Shared camera opening with bounded FFmpeg network operations."""
import sys
import cv2


def open_capture(camera):
    if camera.source_type == 'webcam':
        index = int(camera.url) if camera.url and camera.url.isdigit() else 0
        return cv2.VideoCapture(index, cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY)
    url = camera.url or ''
    if camera.username and camera.password and '://' in url and '@' not in url.split('://', 1)[1]:
        scheme, rest = url.split('://', 1)
        url = f'{scheme}://{camera.username}:{camera.password}@{rest}'
    return cv2.VideoCapture(url, cv2.CAP_FFMPEG, [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000,
        cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000,
    ])
