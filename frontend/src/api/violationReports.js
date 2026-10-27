// Reports only consume GET results. No mutation API is imported here.
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';

export async function collectViolations(getPage, filters) {
  const rows = [];
  let page = 1;
  while (true) {
    const { data } = await getPage({ ...filters, page, per_page: 200 });
    if (!Array.isArray(data.items) || !Number.isInteger(data.total)) throw new Error('Invalid export response');
    rows.push(...data.items);
    if (rows.length >= data.total) return rows;
    if (!data.items.length) throw new Error('Incomplete export response');
    page++;
  }
}

const columns = ['ID', 'Timestamp UTC', 'Violation', 'Source', 'Confidence', 'Review status', 'Acknowledged UTC', 'Escalated UTC', 'Archived UTC', 'Mask assessment', 'Evidence'];
const values = row => [row.id, row.timestamp, row.violation_type, row.source, row.confidence, row.review_status || 'open', row.acknowledged_at, row.escalated_at, row.archived_at, row.mask_assessment, row.screenshot_path];
const csvCell = value => {
  let text = value == null ? '' : String(value);
  // Neutralize spreadsheet formulas as well as escaping quotes/newlines.
  if (/^[\s]*[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
};
export const buildCSV = rows => [columns, ...rows.map(values)].map(row => row.map(csvCell).join(',')).join('\r\n');

export function downloadCSV(rows) {
  const url = URL.createObjectURL(new Blob(['\uFEFF', buildCSV(rows)], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url; link.download = 'safeguard-violations.csv'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function evidenceImage(path) {
  if (!/^\/screenshots\/[^/]+$/.test(path || '')) return null;
  const response = await fetch(path, { signal: AbortSignal.timeout(3000) });
  if (!response.ok) return null;
  const blob = await response.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result); reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

export async function buildPDF(rows, filters, { doc = new jsPDF(), table = autoTable, loadImage = evidenceImage } = {}) {
  doc.setFontSize(18); doc.text('SafeGuard PPE violation report', 14, 18);
  doc.setFontSize(10);
  const summary = ['Helmet', 'Safety Vest', 'Face Mask'].map(ppe => `${ppe}: ${rows.filter(r => (r.missing_ppe || r.violation_type || '').includes(ppe)).length}`).join(' | ');
  doc.text(`Generated UTC: ${new Date().toISOString()}`, 14, 26);
  doc.text(`Records: ${rows.length} | ${summary}`, 14, 33);
  doc.text(doc.splitTextToSize(`Filters: ${JSON.stringify(filters)}`, 180), 14, 40);
  table(doc, { startY: 60, head: [['ID', 'UTC timestamp', 'Missing PPE', 'Source', 'Review status']], body: rows.map(r => [r.id, r.timestamp, r.missing_ppe || r.violation_type, r.source || '', r.review_status || 'open']), styles: { fontSize: 8 } });
  const evidence = new Map();
  rows.forEach(r => { if (r.screenshot_path && !evidence.has(r.screenshot_path)) evidence.set(r.screenshot_path, r.id); });
  let y = 300;
  for (const [path, id] of evidence) {
    if (y > 220) { doc.addPage(); y = 18; doc.text('Evidence thumbnails', 14, y); y += 10; }
    doc.text(`EV-${id}: ${path}`, 14, y);
    try {
      const image = await loadImage(path);
      if (!image) throw new Error('missing');
      doc.addImage(image, 'JPEG', 14, y + 3, 80, 50);
    } catch { doc.text('Evidence image unavailable', 14, y + 12); }
    y += 65;
  }
  return doc;
}
