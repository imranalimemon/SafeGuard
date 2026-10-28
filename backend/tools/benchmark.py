"""Read-only model benchmark using the actual sampled/ACK stream, no DB/network.
Run: python -B backend/tools/benchmark.py --video <file> --frames 120 --output docs/evidence/phase2/benchmark
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))


def describe(values):
    return {'samples': len(values), 'mean': statistics.mean(values) if values else None,
            'p95': sorted(values)[min(len(values)-1, int(len(values)*.95))] if values else None}


async def measure(args, settings, temp):
    import cv2
    from detection.model import PPEDetector
    from detection.violation_logic import compute_violations
    from detection.annotator import annotate_frame
    from websocket.live import LatestFrameStream, send_latest
    from alerts.email_service import preview_email
    detector = PPEDetector(str(args.model.resolve()))
    reference = cv2.VideoCapture(str(args.video))
    ok, first = reference.read()
    fps = reference.get(cv2.CAP_PROP_FPS)
    reference.release()
    if not ok or fps <= 0: raise ValueError('Video must decode and report a positive frame rate.')
    detector.detect(first)  # One warm-up, excluded from timing samples.
    timings, previews, ages = [], [], []
    delivered = []

    class PacedVideo:
        def __init__(self):
            self.cap = cv2.VideoCapture(str(args.video))
            self.next = time.monotonic()
        def isOpened(self): return self.cap.isOpened()
        def read(self):
            time.sleep(max(0, self.next-time.monotonic()))
            self.next = time.monotonic()+1/fps
            ok, frame = self.cap.read()
            if not ok:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self.cap.read()
            return ok, frame
        def release(self): self.cap.release()

    def analyze(frame):
        started = time.perf_counter()
        detections = detector.detect(frame)
        timings.append((time.perf_counter()-started)*1000)
        return detections, compute_violations(detections, frame=frame)

    async def record(frame, result):
        detections, workers = result
        candidates = [w for w in workers if w['status'] == 'VIOLATION']
        if not candidates: return
        screenshot = Path(temp)/'benchmark-evidence.jpg'
        cv2.imwrite(str(screenshot), annotate_frame(frame.copy(), detections, workers))
        data = {'source': 'benchmark:'+args.video.name, 'missing_ppe': candidates[0]['missing_ppe'],
                'timestamp': datetime.now(timezone.utc).isoformat(), 'details': 'Read-only benchmark; no DB row or delivery.'}
        started = time.perf_counter()
        preview = await asyncio.to_thread(preview_email, data, str(screenshot))
        previews.append((time.perf_counter()-started)*1000)
        assert preview['sent'] is False and preview['transport']=='preview'

    def packet(frame, result):
        detections, workers = result if result else ([], [])
        ok, encoded = cv2.imencode('.jpg', annotate_frame(frame.copy(), detections, workers))
        if not ok: raise RuntimeError('JPEG encode failed')
        import base64
        return {'frame': base64.b64encode(encoded).decode()}

    class Finished(Exception): pass
    class Sink:
        def __init__(self): self.acks=asyncio.Queue()
        async def receive_json(self): return await self.acks.get()
        async def send_json(self, message):
            if 'frame' not in message: return
            delivered.append(time.monotonic())
            ages.append(message['frame_age_ms'])
            self.acks.put_nowait({'type':'frame_ack','frame_id':message['frame_id']})
            if len(delivered)>=args.frames: raise Finished()

    stream=LatestFrameStream(PacedVideo, analyze, interval=settings.STREAM_DETECTION_INTERVAL, on_result=record).start()
    try:
        with patch('smtplib.SMTP', side_effect=AssertionError('No SMTP allowed')), patch('smtplib.SMTP_SSL', side_effect=AssertionError('No SMTP allowed')):
            try: await send_latest(Sink(), stream, packet)
            except Finished: pass
            await stream.close()
    finally:
        await stream.close()
    return {'model_sha256':hashlib.sha256(args.model.read_bytes()).hexdigest(),
            'providers': detector.session.get_providers(), 'input_video':str(args.video), 'source_fps':fps,
            'frames_delivered':len(delivered), 'frame_skip':settings.STREAM_DETECTION_INTERVAL,
            'detector_ms':describe(timings), 'delivered_fps':(len(delivered)-1)/(delivered[-1]-delivered[0]),
            'frame_age_ms':describe(ages), 'preview_alert_ms':describe(previews),
            'method':'One warm-up excluded. Paced file replay; actual latest-frame/ACK/JPEG pipeline with an immediate local ACK sink. Excludes browser/network display latency. Preview MIME construction with real detected-violation screenshot; no DB or transports.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--video',type=Path,required=True)
    parser.add_argument('--model',type=Path,default=ROOT/'backend/best.onnx')
    parser.add_argument('--frames',type=int,default=120)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.frames<2: parser.error('--frames must be at least 2')
    with tempfile.TemporaryDirectory(prefix='safeguard-benchmark-') as temp:
        with patch.dict(os.environ, {'SCREENSHOT_DIR':temp,'ALERT_DELIVERY_MODE':'preview','ALERT_EMAIL_FROM':'benchmark@example.invalid','ALERT_EMAIL_TO':'benchmark@example.invalid'}), patch('dotenv.load_dotenv'):
            from config import settings
            result=asyncio.run(measure(args,settings,temp))
    result['command']=' '.join([sys.executable,'-B',*sys.argv])
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'benchmark.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    rows=[('Detector ms',result['detector_ms']['mean']),('Delivered FPS',result['delivered_fps']),('Frame age ms',result['frame_age_ms']['mean']),('Preview alert ms',result['preview_alert_ms']['mean'])]
    table='| Measurement | Mean |\n|---|---:|\n'+''.join(f'| {name} | {value:.3f} |\n' if value is not None else f'| {name} | Not measured: no qualifying violation |\n' for name,value in rows)
    (args.output/'benchmark.md').write_text('# Measured stream benchmark\n\n'+table+'\n'+result['method']+'\n\nCommand: `'+result['command']+'`\n',encoding='utf-8')
    print(table)

if __name__=='__main__': main()
