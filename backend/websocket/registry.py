"""Active streams are isolated by connection; no cross-camera queue or errors."""
import asyncio

streams = {}

def register(camera_id, stream):
    streams[id(stream)] = (camera_id, stream)

def discard(stream):
    streams.pop(id(stream), None)

def status(camera_id):
    states = [stream.status for key, stream in streams.values() if key == camera_id]
    return ', '.join(sorted(set(states))) if states else 'idle'

async def shutdown():
    await asyncio.gather(*(stream.close() for _, stream in list(streams.values())), return_exceptions=True)
    streams.clear()
