// One socket and one displayed frame at a time. Dependencies are injectable for tests.
export function createLiveStream({ openSocket, onState, setTimer = setTimeout, clearTimer = clearTimeout }) {
  let socket = null;
  let timer = null;
  let frameId = null;
  let frameKey = null;
  let generation = 0;

  const stop = () => {
    clearTimer(timer);
    timer = null;
    frameId = null;
    frameKey = null;
    const previous = socket;
    socket = null; // Invalidate callbacks before closing the previous connection.
    previous?.close();
    onState({ isStreaming: false, frame: null, stats: null, error: null });
  };

  const fail = (message) => {
    stop();
    onState({ isStreaming: false, frame: null, stats: null, error: message });
  };

  const start = (cameraId) => {
    stop();
    if (!cameraId) return;
    try {
      const connectionId = ++generation;
      const current = openSocket(cameraId);
      socket = current;
      onState({ isStreaming: true, frame: null, stats: null, error: 'Connecting to camera…' });
      const watch = () => {
        clearTimer(timer);
        timer = setTimer(() => {
          if (socket === current) fail('Camera not available: no recent frames. Press Start to retry.');
        }, 5000);
      };
      watch();
      current.onmessage = (event) => {
        if (socket !== current) return;
        try {
          const data = JSON.parse(event.data);
          if (data.error) { fail(data.error); return; }
          if (data.frame) {
            frameId = data.frame_id;
            frameKey = `${connectionId}:${frameId}`;
            onState({ isStreaming: true, frame: `data:image/jpeg;base64,${data.frame}`, frameKey, stats: data.stats ?? null, error: null });
            watch();
          }
        } catch { fail('Camera not available: invalid stream response.'); }
      };
      current.onerror = () => {
        if (socket === current) fail('Camera not available: could not connect to the stream.');
      };
      current.onclose = () => {
        if (socket === current) fail('Camera not available: stream disconnected. Press Start to retry.');
      };
    } catch { fail('Camera not available: could not connect to the stream.'); }
  };

  return {
    start, stop,
    displayed: (loadedKey) => {
      if (socket && loadedKey === frameKey && frameId != null && socket.readyState === 1) {
        try {
          socket.send(JSON.stringify({ type: 'frame_ack', frame_id: frameId }));
          frameId = null;
        } catch { fail('Camera not available: stream disconnected. Press Start to retry.'); }
      }
    },
    imageError: (loadedKey) => {
      if (loadedKey === frameKey) fail('Camera not available: could not display the frame.');
    },
  };
}

export function cameraTestResult(data) {
  const ok = data?.ok === true;
  return { ok, message: data?.message || data?.error || (ok ? 'Camera test succeeded.' : 'Camera not available: test failed.') };
}
