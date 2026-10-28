// Isolated rendering checks: effects do not run, so no HTTP, camera, or alert calls.
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const Module = require('node:module');
const esbuild = require('esbuild');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const root = path.resolve(__dirname, '..');
const result = esbuild.buildSync({
  stdin: {
    contents: `
      export { LoginForm } from './src/context/Auth';
      export { SystemHealthContext } from './src/context/SystemHealth';
      export { default as Dashboard } from './src/pages/DashboardPage';
      export { default as Footer } from './src/components/layout/Footer';
      export { default as Violations } from './src/pages/ViolationsPage';
      export { ViolationModal } from './src/pages/ViolationsPage';
      export { default as Cameras } from './src/pages/CamerasPage';
      export { CameraCard } from './src/pages/CamerasPage';
      export { ConfigPanel } from './src/pages/CamerasPage';
      export { ReviewState, ReviewActions } from './src/components/ViolationReview';
      export { default as UploadResult } from './src/components/UploadResult';
      export { EmailPreview } from './src/components/EmailPreview';
      export { default as Upload } from './src/pages/UploadPage';
      export { default as Settings } from './src/pages/SettingsPage';
    `,
    resolveDir: root,
  },
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external',
});
const filename = path.join(root, 'test', 'in-memory-status.cjs');
const loaded = new Module(filename, module);
loaded.filename = filename;
loaded.paths = Module._nodeModulePaths(path.dirname(filename));
loaded._compile(result.outputFiles[0].text, filename);
const components = loaded.exports;
global.localStorage = { getItem: () => null };

const offline = { state: 'offline', reachable: false, model_loaded: false, db_connected: false };
const online = {
  state: 'online', reachable: true, model_loaded: true, db_connected: true,
  model_name: 'custom_ppe.onnx', execution_providers: ['CUDAExecutionProvider', 'CPUExecutionProvider'],
};
const render = (name, health) => renderToStaticMarkup(React.createElement(
  components.SystemHealthContext.Provider, { value: health }, React.createElement(components[name]),
));

let html = render('Footer', offline);
assert.match(html, /Offline/);
assert.match(html, /Not available/);
assert.doesNotMatch(html, /Jetson|Orin|YOLOv8s/);
html = render('Footer', online);
assert.match(html, /Online/);
assert.match(html, /custom_ppe\.onnx/);
assert.doesNotMatch(html, /href="#"|Help Desk|Safety Protocols|System Logs/);
assert.match(html, /CUDAExecutionProvider, CPUExecutionProvider/);
assert.match(render('Footer', { ...online, state: 'degraded', db_connected: false }), /Degraded/);
console.log('PASS: footer reflects offline/degraded/online health and supplied model/provider.');

html = render('Dashboard', offline);
assert.match(html, /Backend offline/);
assert.match(html, /Not available/);
assert.doesNotMatch(html, /CAM-0[1-4]|Z-BAY|L-DOC|SECTOR-7|FORGE|128|UNAUTHORIZED ZONE|GPU 0|SYSTEM LOAD/);
assert.match(html, /Incident history not available/);
html = render('Dashboard', online);
assert.match(html, /Live Compliance/);
assert.match(html, /Not available/);
assert.doesNotMatch(html, /0%|94%|CAM-02/);
console.log('PASS: dashboard has no invented data offline or before the first live frame.');

html = render('Violations', online);
assert.equal((html.match(/type="date"/g) || []).length, 2);
assert.match(html, /type="number" min="1" aria-label="Camera ID"/);
assert.doesNotMatch(html, /SITE LOCATION|Sector 7G|Loading Bay A|Loading Bay B|Forge Area|Unauthorized Zone/);
assert.match(render('Cameras', offline), /SYSTEM OFFLINE/);
assert.match(render('Upload', offline), /Model not available/);
assert.doesNotMatch(render('Upload', online), /YOLOv8m|YOLOv8n|Vehicles|Restricted Zones|70%/);
html = render('Settings', offline);
assert.match(html, /Configuration not available/);
assert.doesNotMatch(html, /safety@company\.com|58%/);
console.log('PASS: fake location filters and unsupported model/class choices are absent.');

html = renderToStaticMarkup(React.createElement(components.CameraCard, {
  camera: { id: 1, name: 'Webcam', enabled: true },
  testStatus: { ok: false, message: 'Device index 99 unavailable' },
}));
assert.match(html, /role="alert"/);
assert.match(html, /Device index 99 unavailable/);
console.log('PASS: camera card displays the actual failed test message.');
assert.doesNotMatch(html, /1920.*1080|30 FPS|Resolution|Frame Rate/);
html = renderToStaticMarkup(React.createElement(components.ConfigPanel, {
  form: { name: 'Camera', source_type: 'ip', url: 'http://localhost', location: '', enabled: true },
  formError: 'At most 120 characters', onChange: () => {},
}));
assert.match(html, /role="alert"/);
assert.match(html, /At most 120 characters/);
assert.doesNotMatch(html, /Resolution|Frame Rate|1920.*1080|30 FPS/);
html = renderToStaticMarkup(React.createElement(components.ViolationModal, {
  violation: { id: 7, source: 'camera:42', missing_ppe: 'Helmet', review_status: 'open' },
  onClose: () => {}, onAction: () => {},
}));
assert.match(html, /SOURCE/);
assert.match(html, /camera:42/);
assert.ok(decodeURIComponent(html.match(/href="(https:\/\/api\.whatsapp\.com\/send[^\"]+)"/)[1]).includes('*Camera:* camera:42'));
console.log('PASS: violation detail and quick-share use the actual API source.');

html = renderToStaticMarkup(React.createElement(components.ReviewState, { violation: {
  review_status: 'escalated', acknowledged_at: '2026-10-27T12:00:00', escalated_at: '2026-10-27T12:01:00', archived_at: '2026-10-27T12:02:00', mask_assessment: 'not assessable',
} }));
assert.match(html, /escalated/); assert.match(html, /Acknowledged:/); assert.match(html, /Escalated:/); assert.match(html, /Archived:/); assert.match(html, /Mask: not assessable/);
html = renderToStaticMarkup(React.createElement(components.ReviewActions, { violation: { id: 1 }, onAction: () => {} }));
for (const label of ['Acknowledge', 'Escalate', 'Archive Evidence']) assert.ok(html.includes(label));
html = renderToStaticMarkup(React.createElement(components.ReviewActions, { violation: { review_status: 'escalated', acknowledged_at: 'now', archived_at: 'now' }, onAction: () => {} }));
assert.doesNotMatch(html, /<button/);
for (const file of fs.readdirSync(path.join(root, 'src'), { recursive: true })) {
  if (!/\.(jsx|js)$/.test(file)) continue;
  const source = fs.readFileSync(path.join(root, 'src', file), 'utf8');
  assert.doesNotMatch(source, /coming\s*soon|emergency.stop|\bPTZ\b/i, file);
}
console.log('PASS: review actions/timestamps render and unfinished UI controls are absent.');

const imageWorker = { worker_id: 1, status: 'VIOLATION', ppe_status: { Helmet: 'missing', 'Safety Vest': 'present', 'Face Mask': 'mask not assessable' } };
const created = { id: 42, violation_type: 'Missing: Helmet', timestamp: '2026-10-27T12:00:00', screenshot_path: '/screenshots/evidence.jpg' };
html = renderToStaticMarkup(React.createElement(components.UploadResult, { model: 'best.onnx', result: {
  media_type: 'image', filename: 'worker.png', annotated_image_url: '/screenshots/annotated.jpg', workers: [imageWorker],
  stats: { total_persons: 1, violations: 1, suppressed_by_cooldown: 0 }, created_violations: [created],
} }));
assert.match(html, /src="\/screenshots\/annotated.jpg"/);
assert.match(html, /download="safeguard-annotated.jpg"/);
assert.match(html, /Workers found: 1/);
for (const value of ['Helmet', 'Safety Vest', 'Face Mask', 'missing', 'present', 'mask not assessable', 'EV-42']) assert.ok(html.includes(value));
console.log('PASS: image upload renders annotation, download, workers/PPE states and created records.');

html = renderToStaticMarkup(React.createElement(components.UploadResult, { result: {
  media_type: 'video', total_frames: 9, frames_processed: 4, worker_observations: 8, max_workers_in_frame: 2,
  violations_detected: 4, violations_logged: 1, mask_not_assessable_observations: 2, suppressed_by_cooldown: 3,
  key_frames: [{ frame_number: 3, screenshot_url: '/screenshots/key.jpg', workers: [imageWorker] }],
  violation_frames: [{ frame_number: 3, violations: [imageWorker] }], created_violations: [created],
} }));
assert.match(html, /Frames decoded: 9/); assert.match(html, /Frames analyzed: 4/);
assert.match(html, /Worker observations: 8/); assert.match(html, /not as unique people/);
assert.match(html, /download="safeguard-frame-3.jpg"/);
assert.match(html, /Detected violations by analyzed frame/);
assert.match(html, /Violations created: 1/);
console.log('PASS: video upload renders the real summary, key frames, downloads and violation list.');

html = renderToStaticMarkup(React.createElement(components.EmailPreview, { preview: {
  to: 'configured@example.invalid', subject: 'Camera 7 | 2026-10-28 +05:00 | Missing Helmet',
  body: 'Source: camera:7\nMissing PPE: Helmet', attachments: [{ filename: 'annotated.jpg', bytes: 123 }], eml_base64: 'ZmFrZS1lbWFpbA==',
} }));
assert.match(html, /Nothing was sent/); assert.match(html, /configured@example.invalid/);
assert.match(html, /annotated.jpg/); assert.match(html, /download="safeguard-email-preview.eml"/);
console.log('PASS: email preview shows recipient, exact content, attachment and downloadable MIME without sending.');

html = renderToStaticMarkup(React.createElement(components.LoginForm, { onLogin: () => {}, error: 'Invalid username or password.', busy: true }));
assert.match(html, /type="password"/);
assert.match(html, /autoComplete="current-password"/);
assert.match(html, /for="login-password"/);
assert.match(html, /role="alert"/);
assert.match(html, /disabled=""/);
console.log('PASS: login has labelled password fields, error status and busy state.');
