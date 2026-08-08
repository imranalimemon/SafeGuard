import React, { useState, useEffect, useCallback } from 'react';
import { getViolations, clearViolations } from '../api/client';
import ViolationDetailDrawer from '../components/ViolationDetailDrawer';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';

/**
 * Build a `YYYY-MM-DDTHH:MM:SS` ISO string from a `<input type="date">` value
 * (e.g. "2026-08-01"). The backend's `start_date` / `end_date` params are
 * `Optional[datetime]` and both bounds are inclusive, so we anchor the start
 * at 00:00:00 and the end at 23:59:59 to ensure the entire day is included.
 */
const dateInputToISO = (value, endOfDay = false) => {
  if (!value) return undefined;
  const suffix = endOfDay ? 'T23:59:59' : 'T00:00:00';
  return `${value}${suffix}`;
};

/** Format a `YYYY-MM-DD` range for the page subtitle. */
const formatRangeLabel = (range) => {
  if (!range.start && !range.end) return 'All Time';
  const fmt = (value) => {
    if (!value) return '…';
    const d = new Date(`${value}T00:00:00`);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  };
  return `${fmt(range.start)} – ${fmt(range.end)}`;
};

/** RFC 4180 CSV-cell escaping. Wraps fields containing `,` `"` or newlines in quotes. */
const csvEscape = (value) => {
  if (value === null || value === undefined) return '';
  const s = String(value);
  if (/[",\n\r]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
};

const ViolationsPage = () => {
  const [violations, setViolations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [filterType, setFilterType] = useState('All Types');
  const [dateRange, setDateRange] = useState({ start: null, end: null });
  const [selectedViolationId, setSelectedViolationId] = useState(null);
  const [isExporting, setIsExporting] = useState(false);
  const pageSize = 10;

  const fetchViolations = useCallback(async (range) => {
    setIsLoading(true);
    try {
      const params = { limit: 200, offset: 0 };
      const startISO = dateInputToISO(range.start, false);
      const endISO = dateInputToISO(range.end, true);
      if (startISO) params.start_date = startISO;
      if (endISO) params.end_date = endISO;
      const res = await getViolations(params);
      const data = Array.isArray(res.data) ? res.data : [];
      setViolations(data);
    } catch (error) {
      console.error("Error fetching violations", error);
      setViolations([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchViolations(dateRange);
  }, [dateRange, fetchViolations]);

  // Filter violations (server already filtered by date; only type filter is client-side)
  const filteredViolations = violations.filter(v => {
    if (filterType === 'No Helmet' && !(v.missing_ppe || '').includes('Helmet')) return false;
    if (filterType === 'No Vest' && !(v.missing_ppe || '').includes('Safety Vest')) return false;
    return true;
  });

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filteredViolations.length / pageSize));
  const paginatedViolations = filteredViolations.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [filterType, dateRange]);

  const handleClearAll = async () => {
    if (window.confirm("Are you sure you want to clear all violations? This cannot be undone.")) {
      try {
        await clearViolations();
        setViolations([]);
        setCurrentPage(1);
      } catch (error) {
        console.error("Error clearing violations", error);
      }
    }
  };

  const handleExportCSV = () => {
    if (filteredViolations.length === 0) return;
    const headers = ['ID', 'Timestamp', 'Type', 'Persons', 'Confidence', 'Missing PPE'];
    const rows = filteredViolations.map(v => [
      v.id,
      v.timestamp,
      v.violation_type || '',
      v.person_count || 0,
      v.confidence ? (v.confidence * 100).toFixed(1) + '%' : '',
      v.missing_ppe || ''
    ]);
    // RFC 4180: every cell is escaped; rows are joined with CRLF.
    const csvLines = [
      headers.map(csvEscape).join(','),
      ...rows.map(r => r.map(csvEscape).join(',')),
    ];
    const csvContent = "data:text/csv;charset=utf-8," + encodeURI(csvLines.join('\r\n'));
    const link = document.createElement("a");
    link.setAttribute("href", csvContent);
    link.setAttribute("download", `safeguard_violations_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleExportPDF = async () => {
    if (filteredViolations.length === 0) return;
    if (filteredViolations.length > 100) {
      const ok = window.confirm(
        `This will generate a PDF for ${filteredViolations.length} violations, which may be large. Continue?`
      );
      if (!ok) return;
    }
    setIsExporting(true);
    try {
      const doc = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4' });
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = 40;

      // Title page
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(20);
      doc.setTextColor(11, 19, 38); // sg-background
      doc.text('SafeGuard Violations Report', margin, margin + 10);

      doc.setFont('helvetica', 'normal');
      doc.setFontSize(11);
      doc.setTextColor(90, 65, 54); // sg-outline
      doc.text(`Generated: ${new Date().toLocaleString()}`, margin, margin + 30);
      doc.text(`Range: ${formatRangeLabel(dateRange)}`, margin, margin + 46);
      doc.text(`Filter: ${filterType}`, margin, margin + 62);
      doc.text(`Violations: ${filteredViolations.length}`, margin, margin + 78);

      // Summary table on the cover page
      autoTable(doc, {
        startY: margin + 100,
        head: [['ID', 'Timestamp', 'Type', 'Persons', 'Confidence', 'Missing PPE']],
        body: filteredViolations.map(v => [
          v.id,
          v.timestamp ? new Date(v.timestamp).toLocaleString() : '',
          v.violation_type || '',
          v.person_count ?? 0,
          v.confidence ? (v.confidence * 100).toFixed(1) + '%' : '',
          v.missing_ppe || '',
        ]),
        styles: { fontSize: 8, cellPadding: 4 },
        headStyles: { fillColor: [255, 182, 147], textColor: [86, 31, 0] },
        margin: { left: margin, right: margin },
      });

      // Per-violation detailed pages with embedded screenshot
      for (const v of filteredViolations) {
        doc.addPage();
        let cursorY = margin;

        // Header
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(14);
        doc.setTextColor(11, 19, 38);
        doc.text(`Violation #${v.id}`, margin, cursorY + 10);
        cursorY += 24;

        doc.setFont('helvetica', 'normal');
        doc.setFontSize(10);
        doc.setTextColor(90, 65, 54);
        const meta = [
          ['Timestamp', v.timestamp ? new Date(v.timestamp).toLocaleString() : '-'],
          ['Type', v.violation_type || '-'],
          ['Source', v.source || '-'],
          ['Details', v.details || '-'],
          ['Persons', v.person_count ?? 0],
          ['Confidence', v.confidence ? (v.confidence * 100).toFixed(1) + '%' : '-'],
          ['Missing PPE', v.missing_ppe || '-'],
        ];
        for (const [k, val] of meta) {
          doc.setFont('helvetica', 'bold');
          doc.text(`${k}:`, margin, cursorY + 10);
          doc.setFont('helvetica', 'normal');
          doc.text(String(val), margin + 90, cursorY + 10, { maxWidth: pageWidth - margin * 2 - 90 });
          cursorY += 16;
        }

        // Embed screenshot (skip silently if fetch fails)
        if (v.screenshot_path) {
          try {
            const resp = await fetch(v.screenshot_path);
            if (resp.ok) {
              const blob = await resp.blob();
              const dataUrl = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = reject;
                reader.readAsDataURL(blob);
              });
              cursorY += 12;
              const imgWidth = pageWidth - margin * 2;
              // A4 has ~ (pageHeight - cursorY - margin) remaining — cap to that.
              const imgHeight = Math.min(pageHeight - cursorY - margin, 320);
              doc.addImage(dataUrl, 'JPEG', margin, cursorY, imgWidth, imgHeight);
            }
          } catch (err) {
            console.warn('Failed to embed screenshot for violation', v.id, err);
          }
        }
      }

      doc.save(`safeguard_violations_${new Date().toISOString().slice(0, 10)}.pdf`);
    } catch (err) {
      console.error('PDF export failed', err);
      window.alert('PDF export failed. See console for details.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Page Header Actions */}
      <div className="flex justify-between items-end mb-8">
        <div>
          <h3 className="font-headline-lg text-sg-on-surface mb-1">{filteredViolations.length} Violations</h3>
          <p className="font-body-md text-sg-on-surface-variant">{formatRangeLabel(dateRange)} &bull; {filterType}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleClearAll}
            className="flex items-center gap-2 px-4 py-2 bg-transparent border border-sg-outline-variant text-sg-on-surface rounded hover:bg-sg-surface-container-high hover:border-sg-outline transition-all duration-200"
          >
            <span className="material-symbols-outlined text-sm">delete</span>
            <span className="font-body-md font-medium">Clear All</span>
          </button>
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-2 px-4 py-2 bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface rounded hover:bg-sg-surface-container-high hover:border-sg-outline transition-all duration-200"
          >
            <span className="material-symbols-outlined text-sm">download</span>
            <span className="font-body-md font-medium">Export CSV</span>
          </button>
          <button
            onClick={handleExportPDF}
            disabled={isExporting}
            className="flex items-center gap-2 px-4 py-2 bg-sg-primary text-sg-on-primary font-medium rounded hover:bg-sg-primary-fixed transition-all duration-200 shadow-[0_0_15px_rgba(255,182,147,0.15)] hover:shadow-[0_0_20px_rgba(255,182,147,0.25)] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span className="material-symbols-outlined text-sm">picture_as_pdf</span>
            <span className="font-body-md font-bold">{isExporting ? 'Exporting…' : 'Export PDF'}</span>
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 mb-8 flex-wrap">
        <div className="relative">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="appearance-none bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-body-md rounded-lg pl-4 pr-10 py-2 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors cursor-pointer w-40"
          >
            <option>All Types</option>
            <option>No Helmet</option>
            <option>No Vest</option>
          </select>
          <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-sg-on-surface-variant pointer-events-none text-sm">expand_more</span>
        </div>
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-sg-on-surface-variant pointer-events-none text-base">event</span>
          <input
            type="date"
            value={dateRange.start || ''}
            max={dateRange.end || undefined}
            onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value || null }))}
            className="bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-body-md rounded-lg pl-10 pr-4 py-2 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors [color-scheme:dark]"
            aria-label="Start date"
          />
        </div>
        <span className="font-body-md text-sg-on-surface-variant">→</span>
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-sg-on-surface-variant pointer-events-none text-base">event</span>
          <input
            type="date"
            value={dateRange.end || ''}
            min={dateRange.start || undefined}
            onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value || null }))}
            className="bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-body-md rounded-lg pl-10 pr-4 py-2 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors [color-scheme:dark]"
            aria-label="End date"
          />
        </div>
        {(dateRange.start || dateRange.end) && (
          <button
            onClick={() => setDateRange({ start: null, end: null })}
            className="flex items-center gap-1 px-3 py-2 text-sg-on-surface-variant hover:text-sg-on-surface font-body-md rounded transition-colors"
          >
            <span className="material-symbols-outlined text-sm">close</span>
            Clear
          </button>
        )}
      </div>

      {/* Data Table Container */}
      <div className="bg-sg-surface-container border border-sg-outline-variant rounded-xl overflow-hidden flex flex-col shadow-lg shadow-black/20 flex-1">
        {/* Table Header */}
        <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-sg-outline-variant bg-sg-surface-container-low">
          <div className="col-span-1 font-label-caps text-sg-on-surface-variant">Image</div>
          <div className="col-span-3 font-label-caps text-sg-on-surface-variant">Timestamp</div>
          <div className="col-span-3 font-label-caps text-sg-on-surface-variant">Type</div>
          <div className="col-span-1 font-label-caps text-sg-on-surface-variant text-right">Persons</div>
          <div className="col-span-2 font-label-caps text-sg-on-surface-variant text-right">Confidence</div>
          <div className="col-span-2 font-label-caps text-sg-on-surface-variant">Missing PPE</div>
        </div>

        {/* Table Body */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-16 gap-3">
              <div className="w-5 h-5 border-2 border-sg-primary/30 border-t-sg-primary rounded-full animate-spin"></div>
              <span className="font-body-md text-sg-on-surface-variant">Loading violations...</span>
            </div>
          ) : paginatedViolations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16">
              <span className="material-symbols-outlined text-4xl text-sg-surface-bright mb-3">shield</span>
              <p className="font-body-md text-sg-on-surface-variant">
                {violations.length === 0 ? 'No violations recorded yet.' : 'No violations match your filters.'}
              </p>
            </div>
          ) : (
            paginatedViolations.map((v, idx) => (
              <div
                key={v.id}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedViolationId(v.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setSelectedViolationId(v.id);
                  }
                }}
                className="grid grid-cols-12 gap-4 px-6 py-3 items-center border-b border-sg-outline-variant/50 hover:bg-sg-surface-variant transition-colors duration-150 group border-l-2 border-l-transparent hover:border-l-sg-primary animate-stagger-1 cursor-pointer"
                style={{ animationDelay: `${(idx + 1) * 50}ms` }}
              >
                <div className="col-span-1">
                  <div className="w-12 h-12 rounded border border-sg-outline-variant/50 overflow-hidden relative">
                    {v.screenshot_path ? (
                      <img src={v.screenshot_path} alt="Violation" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full bg-sg-surface-container-lowest flex items-center justify-center">
                        <span className="material-symbols-outlined text-sg-surface-bright text-sm">image</span>
                      </div>
                    )}
                    <div className="absolute inset-0 border border-sg-error/50 pointer-events-none mix-blend-screen"></div>
                  </div>
                </div>
                <div className="col-span-3 font-data-mono text-sg-on-surface">
                  {new Date(v.timestamp).toLocaleString()}
                </div>
                <div className="col-span-3">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-sg-error-container/20 text-sg-error border border-sg-error/30">
                    {v.violation_type || 'Violation'}
                  </span>
                  {v.source && (
                    <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border bg-sg-surface-container-high text-sg-on-surface-variant border-sg-outline-variant">
                      {v.source === 'image_upload' ? 'IMG' : v.source === 'video_upload' ? 'VIDEO' : v.source === 'live_stream' ? 'LIVE' : v.source.toUpperCase()}
                    </span>
                  )}
                </div>
                <div className="col-span-1 font-data-mono text-sg-on-surface text-right">
                  {v.person_count || '-'}
                </div>
                <div className="col-span-2 font-data-mono text-sg-on-surface text-right font-bold">
                  {v.confidence ? Math.round(v.confidence * 100) + '%' : '-'}
                </div>
                <div className="col-span-2 flex items-center justify-between font-body-md text-sg-on-surface-variant">
                  <span className="truncate">{v.missing_ppe || 'None'}</span>
                  <span className="material-symbols-outlined text-sg-on-surface-variant text-base opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-200 ml-2 shrink-0">
                    chevron_right
                  </span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Pagination Footer */}
        <div className="px-6 py-4 border-t border-sg-outline-variant bg-sg-surface-container-low flex items-center justify-between">
          <span className="font-body-md text-sg-on-surface-variant">
            Showing {filteredViolations.length === 0 ? 0 : (currentPage - 1) * pageSize + 1}
            -{Math.min(currentPage * pageSize, filteredViolations.length)} of {filteredViolations.length}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="flex items-center px-3 py-1 rounded bg-sg-surface border border-sg-outline-variant text-sg-on-surface-variant hover:text-sg-on-surface hover:bg-sg-surface-container-high transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-[16px] mr-1">chevron_left</span> Prev
            </button>
            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
              let page;
              if (totalPages <= 5) {
                page = i + 1;
              } else if (currentPage <= 3) {
                page = i + 1;
              } else if (currentPage >= totalPages - 2) {
                page = totalPages - 4 + i;
              } else {
                page = currentPage - 2 + i;
              }
              return (
                <button
                  key={page}
                  onClick={() => setCurrentPage(page)}
                  className={`px-3 py-1 rounded text-sm font-bold transition-colors ${
                    currentPage === page
                      ? 'bg-sg-primary text-sg-on-primary'
                      : 'bg-sg-surface border border-sg-outline-variant text-sg-on-surface-variant hover:text-sg-on-surface hover:bg-sg-surface-container-high'
                  }`}
                >
                  {page}
                </button>
              );
            })}
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="flex items-center px-3 py-1 rounded bg-sg-surface border border-sg-outline-variant text-sg-on-surface-variant hover:text-sg-on-surface hover:bg-sg-surface-container-high transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next <span className="material-symbols-outlined text-[16px] ml-1">chevron_right</span>
            </button>
          </div>
        </div>
      </div>

      <ViolationDetailDrawer
        violationId={selectedViolationId}
        onClose={() => setSelectedViolationId(null)}
      />
    </div>
  );
};

export default ViolationsPage;
