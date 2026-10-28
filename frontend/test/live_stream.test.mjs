// Fake sockets/timers only: no DOM, HTTP, real cameras or alerts.
import assert from 'node:assert/strict';
import test from 'node:test';
import { createLiveStream, cameraTestResult } from '../src/api/liveStream.js';

function harness() {
  const sockets = [], timers = new Map(), states = [];
  let timerId = 0;
  const stream = createLiveStream({
    openSocket: (id) => {
      const socket = {
        id, closed: false, readyState: 1, sent: [],
        close() { this.closed = true; this.onclose?.(); },
        send(value) { this.sent.push(JSON.parse(value)); },
        message(data) { this.onmessage({ data: JSON.stringify(data) }); },
      };
      sockets.push(socket);
      return socket;
    },
    onState: state => states.push(state),
    setTimer: callback => { timers.set(++timerId, callback); return timerId; },
    clearTimer: id => timers.delete(id),
  });
  return { stream, sockets, timers, states, state: () => states.at(-1) };
}

test('switch closes old connection, clears image/stats, and ignores late callbacks', () => {
  const h = harness();
  h.stream.start('1');
  const old = h.sockets[0];
  old.message({ frame: 'old', frame_id: 1, stats: { persons: 2 } });
  h.stream.start('2');
  assert.equal(old.closed, true);
  assert.equal(h.sockets[1].id, '2');
  assert.equal(h.state().frame, null);
  assert.equal(h.state().stats, null);
  old.message({ frame: 'late', frame_id: 2 });
  old.onclose(); old.onerror();
  assert.equal(h.state().error, 'Connecting to camera…');
  h.sockets[1].message({ frame: 'new', frame_id: 10 });
  assert.equal(h.state().frame, 'data:image/jpeg;base64,new');
  assert.equal(h.timers.size, 1);
});

test('switching while still connecting closes previous socket', () => {
  const h = harness();
  h.stream.start('1'); h.stream.start('2'); h.stream.start('3');
  assert.deepEqual(h.sockets.map(s => s.closed), [true, true, false]);
  assert.equal(h.timers.size, 1);
});

test('real backend error remains visible after close, with no reconnect timer', () => {
  const h = harness(); h.stream.start('1');
  h.sockets[0].message({ error: "Camera not available: cannot open camera 'Webcam'" });
  h.sockets[0].onclose();
  assert.match(h.state().error, /cannot open camera 'Webcam'/);
  assert.equal(h.state().isStreaming, false);
  assert.equal(h.state().frame, null);
  assert.equal(h.timers.size, 0);
  assert.equal(h.sockets.length, 1);
});

test('watchdog clears frozen image and allows explicit retry', () => {
  const h = harness(); h.stream.start('1');
  h.sockets[0].message({ frame: 'image', frame_id: 1 });
  [...h.timers.values()][0]();
  assert.equal(h.state().frame, null);
  assert.equal(h.state().isStreaming, false);
  assert.match(h.state().error, /no recent frames/);
  h.stream.start('1');
  assert.equal(h.sockets.length, 2);
});

test('acknowledges only displayed images, once per frame', () => {
  const h = harness(); h.stream.start('1');
  const socket = h.sockets[0];
  socket.message({ frame: 'image', frame_id: 42 });
  assert.deepEqual(socket.sent, []);
  h.stream.displayed(h.state().frameKey); h.stream.displayed(h.state().frameKey);
  assert.deepEqual(socket.sent, [{ type: 'frame_ack', frame_id: 42 }]);
  h.stream.stop(); h.stream.displayed();
  assert.equal(socket.sent.length, 1);
  assert.equal(h.timers.size, 0);
});

test('transport disconnect, malformed messages and image errors clear frames', () => {
  for (const fail of [s => s.onclose(), s => s.onerror(), s => s.onmessage({ data: 'invalid' })]) {
    const h = harness(); h.stream.start('1');
    h.sockets[0].message({ frame: 'image', frame_id: 1 });
    fail(h.sockets[0]);
    assert.equal(h.state().frame, null);
    assert.match(h.state().error, /Camera not available/);
  }
  const h = harness(); h.stream.start('1');
  h.sockets[0].message({ frame: 'image', frame_id: 1 });
  h.stream.imageError(h.state().frameKey);
  assert.match(h.state().error, /could not display/);
});

test('late image loads cannot acknowledge a new camera; identical JPEGs have new display keys', () => {
  const h = harness(); h.stream.start('1');
  h.sockets[0].message({ frame: 'same', frame_id: 1 });
  const oldKey = h.state().frameKey;
  h.stream.start('2');
  const socket = h.sockets[1];
  socket.message({ frame: 'same', frame_id: 1 });
  h.stream.displayed(oldKey);
  h.stream.imageError(oldKey);
  assert.deepEqual(socket.sent, []);
  assert.equal(h.state().isStreaming, true);
  const firstKey = h.state().frameKey;
  h.stream.displayed(firstKey);
  socket.message({ frame: 'same', frame_id: 2 });
  assert.notEqual(h.state().frameKey, firstKey);
  h.stream.displayed(h.state().frameKey);
  assert.deepEqual(socket.sent.map(s => s.frame_id), [1, 2]);
});

test('HTTP 200 body ok:false is failure and preserves actual error message', () => {
  assert.deepEqual(cameraTestResult({ ok: false, message: 'Device index 99 unavailable' }), {
    ok: false, message: 'Device index 99 unavailable',
  });
  assert.equal(cameraTestResult({ ok: 'true' }).ok, false);
  assert.equal(cameraTestResult(null).ok, false);
  assert.deepEqual(cameraTestResult({ ok: true, message: 'Opened webcam 0' }), {
    ok: true, message: 'Opened webcam 0',
  });
});

test('reconnecting status clears stale image and preserves connection until recovery', () => {
  const h = harness(); h.stream.start('1');
  h.sockets[0].message({ frame: 'first', frame_id: 1 });
  h.sockets[0].message({ status: 'reconnecting (1/3)', message: 'Camera reconnecting.' });
  assert.equal(h.state().frame, null);
  assert.equal(h.state().isStreaming, true);
  assert.equal(h.sockets[0].closed, false);
  assert.equal(h.timers.size, 1);
  h.sockets[0].message({ frame: 'recovered', frame_id: 2 });
  assert.equal(h.state().error, null);
  assert.equal(h.state().frame, 'data:image/jpeg;base64,recovered');
});
