import assert from 'node:assert/strict';
import test from 'node:test';
import { collectViolations, buildCSV, buildPDF } from '../src/api/violationReports.js';

test('export collects all matching pages and keeps every current filter', async () => {
  const filters = { date_from: '2026-10-01', date_to: '2026-10-27', camera_id: 7, violation_type: 'Face Mask', review_status: 'acknowledged', archived: true };
  const requests = [];
  const rows = await collectViolations(async params => {
    requests.push(params);
    return { data: { total: 201, items: Array.from({ length: params.page === 1 ? 200 : 1 }, (_, i) => ({ id: (params.page - 1) * 200 + i + 1 })) } };
  }, filters);
  assert.equal(rows.length, 201);
  for (const [i, request] of requests.entries()) assert.deepEqual(request, { ...filters, page: i + 1, per_page: 200 });
});

test('empty exports complete and incomplete server responses fail visibly', async () => {
  assert.deepEqual(await collectViolations(async () => ({ data: { items: [], total: 0 } }), {}), []);
  await assert.rejects(collectViolations(async () => ({ data: { items: [], total: 5 } }), {}), /Incomplete/);
});

test('CSV escapes commas, quotes, newlines and spreadsheet formulas', () => {
  const csv = buildCSV([{ id: 1, violation_type: 'Missing: "Helmet",\nVest', source: '=BAD()', review_status: 'acknowledged', acknowledged_at: '2026-10-27T12:00:00' }]);
  assert.match(csv, /"Missing: ""Helmet"",\nVest"/);
  assert.ok(csv.includes('"\'=BAD()"'));
  assert.match(csv, /acknowledged/);
  assert.match(csv, /2026-10-27T12:00:00/);
});

test('PDF has summary, filtered table and evidence; missing thumbnails do not abort', async () => {
  const calls = [], tables = [];
  const doc = {
    setFontSize: () => {}, setFillColor: () => {}, rect: (...args) => calls.push(["bar", ...args]), text: (...args) => calls.push(args),
    splitTextToSize: text => text, addPage: () => calls.push(['page']),
    addImage: (...args) => calls.push(['image', ...args]),
  };
  const rows = [
    { id: 1, timestamp: '2026-10-27', missing_ppe: 'Helmet', source: 'camera:7', review_status: 'escalated', screenshot_path: '/screenshots/one.jpg' },
    { id: 2, missing_ppe: 'Face Mask', screenshot_path: '/screenshots/missing.jpg' },
  ];
  const report = await buildPDF(rows, { camera_id: 7 }, {
    doc, table: (doc, options) => tables.push(options),
    loadImage: async path => path.includes('missing') ? null : 'data:image/jpeg;base64,example',
  });
  assert.equal(report, doc);
  assert.match(calls.flat().join(' '), /Records: 2/);
  assert.match(calls.flat().join(' '), /camera_id/);
  assert.match(calls.flat().join(' '), /Evidence image unavailable/);
  assert.ok(calls.some(call => call[0] === 'bar'));
  assert.match(calls.flat().join(' '), /Date range UTC/);
  assert.equal(tables[0].body.length, 2);
  assert.equal(tables[0].body[0][4], 'escalated');
  assert.equal(calls.filter(call => call[0] === 'image').length, 1);
});

test('real PDF generation creates a PDF document without a browser or download', async () => {
  const doc = await buildPDF([{ id: 106, violation_type: 'Missing: Helmet', review_status: 'open' }], { archived: false });
  assert.match(doc.output(), /^%PDF-/);
  assert.match(doc.output(), /SafeGuard PPE violation report/);
});
