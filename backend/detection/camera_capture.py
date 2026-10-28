"""Shared camera opening with bounded FFmpeg network operations."""
import sys
import cv2
try:
    from credentials import reveal
except ModuleNotFoundError:
    from backend.credentials import reveal


def open_capture(camera):
    if camera.source_type == 'webcam':
        index = int(camera.url) if camera.url and camera.url.isdigit() else 0
        return cv2.VideoCapture(index, cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY)
    url = reveal(camera.url) or ''
    username, password = reveal(camera.username), reveal(camera.password)
    if username and password and '://' in url and '@' not in url.split('://', 1)[1]:
        from urllib.parse import quote
        scheme, rest = url.split('://', 1)
        url = f'{scheme}://{quote(username, safe="")}:{quote(password, safe="")}@{rest}'
    return cv2.VideoCapture(url, cv2.CAP_FFMPEG, [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000,
        cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000,
    ])
