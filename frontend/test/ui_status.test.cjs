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
      export { SystemHealthContext } from './src/context/SystemHealth';
      export { default as Dashboard } from './src/pages/DashboardPage';
      export { default as Footer } from './src/components/layout/Footer';
      export { default as Violations } from './src/pages/ViolationsPage';
      export { default as Cameras } from './src/pages/CamerasPage';
      export { CameraCard } from './src/pages/CamerasPage';
      export { ReviewState, ReviewActions } from './src/components/ViolationReview';
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
