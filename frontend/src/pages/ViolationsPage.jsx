import React, { useState, useEffect, useCallback } from 'react';
import { getViolations, clearViolations } from '../api/client';

const VIOLATION_TYPES = ['All Types', 'Missing Helmet', 'No High-Vis Vest', 'Unauthorized Zone', 'Missing PPE', 'Camera Obscured'];
const LOCATIONS       = ['Sector 7G', 'Loading Bay A', 'Loading Bay B', 'Main Gate', 'Forge Area'];

/* ── Severity badge ──────────────────────────────────────── */
const ViolationBadge = ({ type }) => {
  const lc = (type || '').toLowerCase();
  const isCamera = lc.includes('camera') || lc.includes('obscured');
  const style = isCamera
    ? { bg: '#313540', border: 'rgba(90,65,54,0.5)', color: '#bcc7de', icon: 'visibility_off' }
    : { bg: 'rgba(147,0,10,0.25)', border: 'rgba(255,180,171,0.3)', color: '#ffb4ab', icon: 'warning' };
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-data-value"
      style={{ background: style.bg, border: `1px solid ${style.border}`, color: style.color, fontSize: '11px' }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: '12px' }}>{style.icon}</span>
      {type}
    </span>
  );
};

/* ── Detail Modal ────────────────────────────────────────── */
const ViolationModal = ({ violation, onClose }) => {
  if (!violation) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-8 animate-fade-in"
      style={{ background: 'rgba(15,19,29,0.92)', backdropFilter: 'blur(6px)' }}
      onClick={onClose}
    >
      <div
        className="rounded-xl max-w-4xl w-full flex flex-col overflow-hidden"
        style={{ background: '#0b0f19', border: '1px solid #334155', boxShadow: '0 25px 50px rgba(0,0,0,0.5)', borderLeft: '2px solid #FF6B00', maxHeight: '90vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="px-5 py-3 flex justify-between items-center" style={{ background: '#1c1f2a', borderBottom: '1px solid #334155' }}>
          <h3 className="font-headline-md" style={{ color: '#fff', fontSize: '18px' }}>
            Violation Detail: EV-{violation.id || '---'}
          </h3>
          <button onClick={onClose} className="hover:text-white transition-colors" style={{ color: '#94A3B8' }}>
            <span className="material-symbols-outlined" style={{ fontSize: '22px' }}>close</span>
          </button>
        </div>

        <div className="flex flex-col md:flex-row flex-1 min-h-0">
          {/* Image area */}
          <div className="flex-1 bg-black flex items-center justify-center relative p-4 min-h-48">
            {violation.screenshot_path ? (
              <img src={violation.screenshot_path} alt="Violation evidence" className="max-w-full max-h-full object-contain" style={{ border: '1px solid #334155' }} />
            ) : (
              <div className="flex flex-col items-center" style={{ color: '#313540' }}>
                <span className="material-symbols-outlined mb-2" style={{ fontSize: '48px' }}>image_not_supported</span>
                <span className="font-data-label" style={{ color: '#94A3B8', fontSize: '11px' }}>No evidence image</span>
              </div>
            )}
            {/* Zoom controls overlay */}
            <div className="absolute bottom-5 left-1/2 -translate-x-1/2 glass-panel rounded-full px-4 py-2 flex gap-3 items-center">
              {['zoom_in', 'zoom_out', 'file_download'].map((icon) => (
                <button key={icon} className="hover:text-orange-400 transition-colors" style={{ color: '#fff' }}>
                  <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>{icon}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Metadata panel */}
          <div className="w-72 flex-shrink-0 flex flex-col gap-5 p-5 overflow-y-auto" style={{ background: '#1c1f2a', borderLeft: '1px solid #334155' }}>
            <div>
              <div className="font-data-label mb-1" style={{ color: '#94A3B8', fontSize: '10px' }}>VIOLATION TYPE</div>
              <ViolationBadge type={violation.violation_type || 'Unknown'} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: 'CONFIDENCE', value: violation.confidence != null ? `${Math.round(violation.confidence * 100)}%` : '—', color: '#FF6B00' },
                { label: 'CAMERA ID', value: violation.camera_id || violation.camera_name || '—', color: '#dfe2f1' },
              ].map(({ label, value, color }) => (
                <div key={label}>
                  <div className="font-data-label mb-1" style={{ color: '#94A3B8', fontSize: '10px' }}>{label}</div>
                  <div className="font-data-value" style={{ color, fontSize: '14px' }}>{value}</div>
                </div>
              ))}
              <div className="col-span-2">
                <div className="font-data-label mb-1" style={{ color: '#94A3B8', fontSize: '10px' }}>TIMESTAMP</div>
                <div className="font-data-value" style={{ color: '#dfe2f1', fontSize: '12px' }}>
                  {violation.timestamp ? new Date(violation.timestamp).toLocaleString() : '—'}
                </div>
              </div>
              {violation.location_name && (
                <div className="col-span-2">
                  <div className="font-data-label mb-1" style={{ color: '#94A3B8', fontSize: '10px' }}>LOCATION</div>
                  <div className="font-data-value" style={{ color: '#dfe2f1', fontSize: '12px' }}>{violation.location_name}</div>
                </div>
              )}
            </div>
            <div>
              <div className="font-data-label mb-2" style={{ color: '#94A3B8', fontSize: '10px' }}>ACTIONS</div>
              <div className="flex flex-col gap-2">
                <button
                  className="w-full py-2 rounded font-data-value transition-colors"
                  style={{ background: '#1c1f2a', border: '1px solid #334155', color: '#dfe2f1', fontSize: '12px' }}
                >
                  Mark False Positive
                </button>
                <button
                  className="w-full py-2 rounded font-data-value font-bold transition-opacity hover:opacity-90"
                  style={{ background: '#FF6B00', color: '#000', fontSize: '12px' }}
                >
                  Export to Incident Report
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ══════════════════════════════════════════════════════════ */
const ViolationsPage = () => {
  const [violations, setViolations]       = useState([]);
  const [total, setTotal]                 = useState(0);
  const [isLoading, setIsLoading]         = useState(true);
  const [selected, setSelected]           = useState(null);
  const [page, setPage]                   = useState(1);
  const PAGE_SIZE = 20;

  /* Filter state */
  const [dateFrom, setDateFrom]           = useState('');
  const [dateTo, setDateTo]               = useState('');
  const [violationType, setViolationType] = useState('All Types');
  const [cameraId, setCameraId]           = useState('');
  const [locations, setLocations]         = useState({});

  const fetchViolations = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = {
        page,
        per_page: PAGE_SIZE,
        ...(dateFrom           && { date_from: dateFrom }),
        ...(dateTo             && { date_to: dateTo }),
        ...(violationType !== 'All Types' && { violation_type: violationType }),
        ...(cameraId.trim()   && { camera_id: cameraId.trim() }),
      };
      const res = await getViolations(params);
      const data = res.data;
      if (Array.isArray(data)) {
        setViolations(data);
        setTotal(data.length);
      } else {
        setViolations(data.violations ?? data.items ?? []);
        setTotal(data.total ?? 0);
      }
    } catch { setViolations([]); }
    finally { setIsLoading(false); }
  }, [page, dateFrom, dateTo, violationType, cameraId]);

  useEffect(() => { fetchViolations(); }, [fetchViolations]);

  const applyFilters = () => { setPage(1); fetchViolations(); };
  const resetFilters = () => {
    setDateFrom(''); setDateTo(''); setViolationType('All Types'); setCameraId(''); setLocations({});
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <div className="flex h-full overflow-hidden" style={{ background: '#0b0f19' }}>

        {/* ── Filter Sidebar ─────────────────────────────────── */}
        <aside
          className="w-72 flex flex-col flex-shrink-0 overflow-y-auto"
          style={{ background: 'rgba(30,41,59,0.6)', backdropFilter: 'blur(12px)', borderRight: '1px solid #334155' }}
        >
          <div className="px-4 py-3 flex justify-between items-center" style={{ background: '#171b26', borderBottom: '1px solid #334155' }}>
            <h3 className="font-headline-sm" style={{ color: '#dfe2f1', fontSize: '16px' }}>Filters</h3>
            <button onClick={resetFilters} className="font-data-label hover:text-white transition-colors" style={{ color: '#94A3B8', fontSize: '11px' }}>RESET</button>
          </div>

          <div className="p-4 flex flex-col gap-5">

            {/* Time Range */}
            <div>
              <label className="block font-data-label mb-2" style={{ color: '#94A3B8', fontSize: '10px' }}>TIME RANGE</label>
              <div className="flex flex-col gap-2">
                {[
                  { val: dateFrom, set: setDateFrom, placeholder: 'From: YYYY-MM-DD' },
                  { val: dateTo,   set: setDateTo,   placeholder: 'To: YYYY-MM-DD'   },
                ].map(({ val, set, placeholder }, i) => (
                  <div key={i} className="relative">
                    <span className="material-symbols-outlined absolute left-2 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: '#94A3B8', fontSize: '14px' }}>calendar_month</span>
                    <input
                      type="text"
                      value={val}
                      onChange={(e) => set(e.target.value)}
                      placeholder={placeholder}
                      className="w-full rounded pl-8 pr-2 py-1.5 font-data-value outline-none"
                      style={{ background: '#020617', border: '1px solid #334155', color: '#dfe2f1', fontSize: '11px' }}
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Violation Type */}
            <div>
              <label className="block font-data-label mb-2" style={{ color: '#94A3B8', fontSize: '10px' }}>VIOLATION TYPE</label>
              <select
                value={violationType}
                onChange={(e) => setViolationType(e.target.value)}
                className="w-full rounded px-2 py-1.5 font-data-value outline-none"
                style={{ background: '#020617', border: '1px solid #334155', color: '#dfe2f1', fontSize: '12px' }}
              >
                {VIOLATION_TYPES.map((t) => <option key={t}>{t}</option>)}
              </select>
            </div>

            {/* Camera ID */}
            <div>
              <label className="block font-data-label mb-2" style={{ color: '#94A3B8', fontSize: '10px' }}>CAMERA ID</label>
              <input
                type="text"
                value={cameraId}
                onChange={(e) => setCameraId(e.target.value)}
                placeholder="e.g. CAM-01"
                className="w-full rounded px-2 py-1.5 font-data-value outline-none"
                style={{ background: '#020617', border: '1px solid #334155', color: '#dfe2f1', fontSize: '12px' }}
              />
            </div>

            {/* Site Location */}
            <div>
              <label className="block font-data-label mb-2" style={{ color: '#94A3B8', fontSize: '10px' }}>SITE LOCATION</label>
              <div className="flex flex-col gap-2">
                {LOCATIONS.map((loc) => (
                  <label key={loc} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={!!locations[loc]}
                      onChange={() => setLocations((l) => ({ ...l, [loc]: !l[loc] }))}
                      style={{ accentColor: '#FF6B00' }}
                    />
                    <span className="font-data-label" style={{ color: '#dfe2f1', fontSize: '12px' }}>{loc}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>

          <div className="p-4 mt-auto" style={{ borderTop: '1px solid #334155' }}>
            <button
              onClick={applyFilters}
              className="w-full py-2 rounded font-data-value uppercase tracking-wider transition-colors"
              style={{ background: '#334155', color: '#fff', fontSize: '12px', fontWeight: 700 }}
            >
              APPLY FILTERS
            </button>
          </div>
        </aside>

        {/* ── Main Data Area ─────────────────────────────────── */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

          {/* Header bar */}
          <div
            className="p-4 flex justify-between items-center flex-shrink-0 status-bar-alert"
            style={{ background: 'rgba(30,41,59,0.6)', backdropFilter: 'blur(12px)', border: '1px solid #334155', margin: '8px', borderRadius: '8px' }}
          >
            <div>
              <div className="font-headline-md font-bold" style={{ color: '#fff', fontSize: '20px' }}>
                {isLoading ? '…' : total} Violations Found
              </div>
              <div className="font-data-label mt-1" style={{ color: '#94A3B8', fontSize: '11px' }}>
                {violationType !== 'All Types' ? `Filtered by: ${violationType}` : 'Showing all violations'}
              </div>
            </div>
            <div className="flex gap-2">
              {[
                { icon: 'delete',       label: 'Archive Evidence' },
                { icon: 'download',     label: 'Export CSV' },
              ].map(({ icon, label }) => (
                <button key={label} className="flex items-center gap-2 px-4 py-2 rounded font-body-sm transition-colors" style={{ border: '1px solid #94A3B8', color: '#dfe2f1', background: 'transparent', fontSize: '13px' }}>
                  <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>{icon}</span>
                  {label}
                </button>
              ))}
              <button
                onClick={() => { if (window.confirm('Clear all violations?')) clearViolations().then(fetchViolations); }}
                className="flex items-center gap-2 px-4 py-2 rounded font-body-sm font-bold transition-opacity hover:opacity-90"
                style={{ background: '#FF6B00', color: '#000', fontSize: '13px' }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>picture_as_pdf</span>
                Export PDF Report
              </button>
            </div>
          </div>

          {/* Table */}
          <div
            className="flex-1 flex flex-col overflow-hidden mx-2 mb-2 rounded-lg"
            style={{ background: 'rgba(30,41,59,0.6)', backdropFilter: 'blur(12px)', border: '1px solid #334155' }}
          >
            <div className="overflow-auto flex-1">
              <table className="w-full text-left border-collapse">
                <thead style={{ background: '#171b26', position: 'sticky', top: 0, zIndex: 10, borderBottom: '1px solid #334155' }}>
                  <tr>
                    {['EVIDENCE', 'TIMESTAMP (UTC)', 'VIOLATION TYPE', 'CAMERA / LOC', 'CONFIDENCE', 'ACTION'].map((h, i) => (
                      <th key={h} className="p-3 font-data-label" style={{ color: '#94A3B8', fontSize: '11px', textAlign: i === 5 ? 'right' : 'left' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="font-data-value" style={{ color: '#dfe2f1' }}>
                  {isLoading ? (
                    <tr><td colSpan={6} className="p-8 text-center font-data-label" style={{ color: '#94A3B8' }}>Loading…</td></tr>
                  ) : violations.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="p-12 text-center">
                        <span className="material-symbols-outlined mb-3 block" style={{ fontSize: '40px', color: '#313540' }}>inventory_2</span>
                        <p className="font-data-label" style={{ color: '#94A3B8' }}>No violations found</p>
                      </td>
                    </tr>
                  ) : (
                    violations.map((v, i) => (
                      <tr
                        key={v.id ?? i}
                        onClick={() => setSelected(v)}
                        className="zebra-row cursor-pointer transition-colors hover:bg-surface-container"
                        style={{ borderBottom: '1px solid rgba(51,65,85,0.4)' }}
                      >
                        <td className="p-3">
                          {v.screenshot_path ? (
                            <img src={v.screenshot_path} alt="evidence" className="w-16 h-12 object-cover rounded-sm" style={{ border: '1px solid #334155' }} />
                          ) : (
                            <div className="w-16 h-12 rounded-sm flex items-center justify-center" style={{ background: '#262a35', border: '1px solid #334155' }}>
                              <span className="material-symbols-outlined" style={{ fontSize: '16px', color: '#94A3B8' }}>broken_image</span>
                            </div>
                          )}
                        </td>
                        <td className="p-3" style={{ fontSize: '12px' }}>{v.timestamp ? new Date(v.timestamp).toLocaleString() : '—'}</td>
                        <td className="p-3"><ViolationBadge type={v.violation_type || 'Unknown'} /></td>
                        <td className="p-3" style={{ color: '#94A3B8', fontSize: '12px' }}>
                          {v.camera_id || v.camera_name || '—'}
                          {v.location_name && <><br /><span style={{ fontSize: '11px', color: 'rgba(148,163,184,0.7)' }}>{v.location_name}</span></>}
                        </td>
                        <td className="p-3">
                          <span style={{ color: v.confidence != null ? '#FF6B00' : '#94A3B8', fontSize: '13px' }}>
                            {v.confidence != null ? `${Math.round(v.confidence * 100)}%` : 'N/A'}
                          </span>
                        </td>
                        <td className="p-3 text-right">
                          <button className="p-1 transition-colors hover:text-white" style={{ color: '#94A3B8' }}>
                            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>open_in_new</span>
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="p-3 flex justify-between items-center flex-shrink-0" style={{ background: '#171b26', borderTop: '1px solid #334155' }}>
              <span className="font-data-label" style={{ color: '#94A3B8', fontSize: '11px' }}>
                Showing {((page - 1) * PAGE_SIZE) + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
              </span>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-2 py-1 rounded font-data-label disabled:opacity-40"
                  style={{ border: '1px solid #334155', color: '#94A3B8', fontSize: '11px', background: 'transparent' }}
                >
                  PREV
                </button>
                {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className="px-2 py-1 rounded font-data-label"
                    style={{
                      border: page === p ? '1px solid #FF6B00' : '1px solid #334155',
                      background: page === p ? 'rgba(255,107,0,0.1)' : 'transparent',
                      color: page === p ? '#FF6B00' : '#94A3B8',
                      fontSize: '11px',
                    }}
                  >
                    {p}
                  </button>
                ))}
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="px-2 py-1 rounded font-data-label disabled:opacity-40"
                  style={{ border: '1px solid #334155', color: '#94A3B8', fontSize: '11px', background: 'transparent' }}
                >
                  NEXT
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Detail Modal */}
      {selected && <ViolationModal violation={selected} onClose={() => setSelected(null)} />}
    </>
  );
};

export default ViolationsPage;
