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
  doc.setFontSize(22); doc.text('SafeGuard PPE violation report', 14, 28);
  doc.setFontSize(12); doc.text('Construction safety review', 14, 40);
  doc.setFontSize(10);
  const stamps = rows.map(row => row.timestamp).filter(Boolean).sort();
  const range = `${filters.date_from || stamps[0]?.slice(0,10) || 'Not available'} to ${filters.date_to || stamps.at(-1)?.slice(0,10) || 'Not available'}`;
  doc.text(`Date range UTC: ${range}`, 14, 55);
  doc.text(`Generated UTC: ${new Date().toISOString()}`, 14, 64);
  doc.text(`Records: ${rows.length}`, 14, 73);
  doc.text(doc.splitTextToSize(`Active filters: ${JSON.stringify(filters)}`, 180), 14, 84);
  doc.text('Recorded incidents support human review; observations are not unique workers.',14,112);
  doc.addPage();
  doc.setFontSize(16); doc.text('Summary of filtered records',14,20);
  const ppe = ['Helmet','Safety Vest','Face Mask'].map(name => [name, rows.filter(row => (row.missing_ppe || row.violation_type || '').includes(name)).length]);
  const review = Object.entries(rows.reduce((counts,row)=>{const name=row.review_status||'open';counts[name]=(counts[name]||0)+1;return counts;},{}));
  const chart = (title, entries, top) => {
    doc.setFontSize(11); doc.text(title,14,top);
    if (!entries.length) { doc.text('No matching records.',14,top+10); return; }
    const maximum=Math.max(1,...entries.map(([,count])=>count));
    entries.forEach(([label,count],index)=>{
      const y=top+8+index*13;
      doc.setFontSize(9);doc.text(String(label),14,y+4);
      doc.setFillColor(255,107,0);doc.rect(70,y,100*count/maximum,6,'F');
      doc.text(String(count),175,y+4);
    });
  };
  chart('Missing PPE (a record can contain several items)',ppe,35);
  chart('Review status',review,100);
  const byDay=Object.entries(rows.reduce((counts,row)=>{if(row.timestamp){const day=row.timestamp.slice(0,10);counts[day]=(counts[day]||0)+1;}return counts;},{})).sort(([a],[b])=>a.localeCompare(b));
  // Paginate date charts so a long report never clips daily counts.
  for(let offset=0;offset<byDay.length;offset+=14){doc.addPage();chart('Recorded violations by day (UTC)',byDay.slice(offset,offset+14),20);}
  doc.addPage();doc.setFontSize(16);doc.text('Filtered incident table',14,20);
  table(doc, { startY: 30, head: [['ID', 'UTC timestamp', 'Missing PPE', 'Source', 'Review status']], body: rows.map(r => [r.id, r.timestamp, r.missing_ppe || r.violation_type, r.source || '', r.review_status || 'open']), styles: { fontSize: 8 } });
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
