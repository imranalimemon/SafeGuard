import Analytics from '../components/Analytics';
import React, { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { getDashboardStats, listCameras, reviewViolation } from '../api/client';
import { useSystemHealth } from '../context/SystemHealth';
import { createLiveStream } from '../api/liveStream';

import { ReviewActions, ReviewState } from '../components/ViolationReview';

const SELECTED_CAMERA_KEY = 'sg_selected_camera';

/* ── tiny helpers ─────────────────────────────────────────── */
const Gauge = ({ label, value, color = '#10B981', icon = 'verified_user' }) => (
  <div
    className="rounded p-4 relative overflow-hidden"
    style={{ background: 'var(--color-surface)', border: '1px solid var(--color-outline-variant)' }}
  >
    <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l" style={{ background: color }} />
    <div className="flex justify-between items-center mb-3 pl-2">
      <h3 className="font-headline-sm" style={{ color: 'var(--color-on-surface)', fontSize: '16px' }}>{label}</h3>
      <span className="material-symbols-outlined" style={{ color, fontSize: '20px' }}>{icon}</span>
    </div>
    <div className="pl-2 flex items-end gap-1 mb-3">
      <span style={{ fontFamily: 'Geist, sans-serif', fontWeight: 700, fontSize: '40px', color: 'var(--color-on-surface)', lineHeight: 1 }}>{value}</span>
      {typeof value === 'number' && <span className="font-data-value mb-1" style={{ color: 'var(--color-on-surface-variant)' }}>%</span>}
    </div>
    {typeof value === 'number' && <div className="pl-2 w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--color-surface-container-high)' }}>
      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${Math.min(value, 100)}%`, background: color }} />
    </div>}
  </div>
);

const StatTile = ({ label, value, accent = false }) => (
  <div
    className="rounded p-4 relative"
    style={{ background: 'var(--color-surface)', border: '1px solid var(--color-outline-variant)' }}
  >
    {accent && <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l" style={{ background: '#FF2D55' }} />}
    <div className={accent ? 'pl-2' : ''}>
      <div className="font-data-label mb-2" style={{ color: 'var(--color-on-surface-variant)' }}>{label}</div>
      <div
        className="font-headline-md"
        style={{ color: accent ? '#FF2D55' : 'var(--color-on-surface)', fontSize: typeof value === 'string' ? '16px' : '22px', overflowWrap: 'anywhere', fontFamily: 'Geist, sans-serif', fontWeight: 600, ...(accent ? { animation: 'pulse 2s infinite' } : {}) }}
      >
        {value}
      </div>
    </div>
  </div>
);

const IncidentItem = ({ violation, onAction, busy }) => (
  <div className="p-3" style={{ borderBottom: '1px solid var(--color-outline-variant)' }}>
    <div>{violation.violation_type}</div>
      <div>{violation.source || 'Source not available'} | {violation.timestamp} UTC</div>
    <ReviewState violation={violation} />
    <ReviewActions violation={violation} onAction={onAction} busy={busy} />
  </div>
);

const DashboardPage = () => {
  const health = useSystemHealth();
  const [isStreaming, setIsStreaming] = useState(false);
  const [frame, setFrame] = useState(null);
  const [frameKey, setFrameKey] = useState(null);
  const [liveStats, setLiveStats] = useState(null);
  const [stats, setStats] = useState(null);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [statsError, setStatsError] = useState(null);
  const [streamError, setStreamError] = useState(null);
  const [camerasLoaded, setCamerasLoaded] = useState(false);
  const [cameras, setCameras] = useState([]);
  const [selectedCameraId, setSelectedCameraId] = useState(
    () => localStorage.getItem(SELECTED_CAMERA_KEY) || null
  );
  const streamRef = useRef(null);
  if (!streamRef.current) {
    streamRef.current = createLiveStream({
      openSocket: (cameraId) => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return new WebSocket(`${protocol}//${window.location.host}/ws/stream/${cameraId}`);
      },
      onState: (state) => {
        setIsStreaming(state.isStreaming); setFrame(state.frame);
        setFrameKey(state.frameKey ?? null);
        setLiveStats(state.stats); setStreamError(state.error);
      },
    });
  }

  /* ── fetch ─────────────────────────── */
  const fetchStats = async () => {
    try {
      const res = await getDashboardStats();
      if (!Array.isArray(res.data?.recent_violations)) throw new Error('Invalid statistics response');
      setStats(res.data);
      setStatsError(null);
    } catch { setStats(null); setStatsError('Violation history is not available.'); }
  };

  const handleReview = async (id, action) => {
    setReviewBusy(true); setActionError(null);
    try { await reviewViolation(id, action); await fetchStats(); }
    catch (err) { setActionError(err.response?.data?.detail || 'Could not save review action.'); }
    finally { setReviewBusy(false); }
  };

  const fetchCameras = async () => {
    try {
      const res = await listCameras();
      if (!Array.isArray(res.data)) throw new Error('Invalid camera response');
      const data = res.data;
      setCameras(data);
      setCamerasLoaded(true);
      setSelectedCameraId((current) => {
        if (current && data.find((c) => c.id === Number(current) && c.enabled)) return current;
        const first = data.find((c) => c.enabled);
        const next = first ? String(first.id) : null;
        if (next) localStorage.setItem(SELECTED_CAMERA_KEY, next);
        return next;
      });
    } catch { setCameras([]); setCamerasLoaded(false); }
  };

  /* ── stream ─────────────────────────── */
  const startStream = (cameraId = selectedCameraId) => streamRef.current.start(cameraId);
  const stopStream = () => streamRef.current.stop();

  const handleCameraChange = (e) => {
    const id = e.target.value || null;
    setSelectedCameraId(id);
    if (id) localStorage.setItem(SELECTED_CAMERA_KEY, id);
    stopStream();
    if (id && health.state === 'online') startStream(id);
  };

  useEffect(() => {
    if (!health.reachable) {
      stopStream(); setStats(null); setStatsError(null); setCameras([]); setCamerasLoaded(false);
      return undefined;
    }
    fetchStats(); fetchCameras();
    const timer = setInterval(fetchStats, 10000);
    return () => clearInterval(timer);
  }, [health.reachable]);

  useEffect(() => () => streamRef.current.stop(), []);

  /* ── recent violations → incident log ─ */
  const history = health.reachable ? stats : null;
  const current = health.state === 'online' && frame ? liveStats : null;
  const recentViolations = history?.recent_violations ?? [];

  return (
    <div className="dashboard-layout flex flex-wrap h-full overflow-auto">

      {/* One selected, configured camera; no placeholder camera slots. */}
      <section className="dashboard-live flex-1 min-w-0 flex flex-col gap-2 p-4 h-full overflow-hidden">
        {health.state === 'offline' && <p role="status">Backend offline. Live data is not available.</p>}
        {health.state === 'degraded' && <p role="status">Backend reachable, but {!health.model_loaded ? 'model is unavailable' : 'database is unavailable'}.</p>}
        {actionError && <p role="alert">{actionError}</p>}
        {statsError && health.reachable && <p role="alert">{statsError}</p>}

        {/* Selected camera feed; annotations are already drawn by the backend. */}
        <div className="relative flex-1 rounded overflow-hidden group" style={{ border: `1px solid #FF6B00`, background: 'var(--color-surface)', minHeight: 0 }}>
          <div className="absolute inset-0 scanline z-10 pointer-events-none" />
          {isStreaming && frame ? (
            <img key={frameKey} src={frame} onLoad={() => streamRef.current.displayed(frameKey)} onError={() => streamRef.current.imageError(frameKey)} alt="Live feed" className="absolute inset-0 w-full h-full object-contain" />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ background: 'rgba(248,250,252,0.92)' }}>
              <span className="material-symbols-outlined mb-3" style={{ color: 'var(--color-on-surface-variant)', fontSize: '40px' }}>videocam_off</span>
              <p className="font-data-label" style={{ color: 'var(--color-on-surface-variant)' }}>{streamError || (health.state === 'offline' ? 'BACKEND OFFLINE' : 'NO LIVE CAMERA FRAMES')}</p>
              {camerasLoaded && cameras.length === 0 && (
                <Link to="/cameras" className="mt-3 font-data-label" style={{ color: '#FF6B00', textDecoration: 'underline' }}>
                  Add a camera →
                </Link>
              )}
            </div>
          )}

          {/* Top bar */}
          <div className="absolute top-0 left-0 w-full p-3 flex justify-between items-start z-20" style={{ background: 'linear-gradient(to bottom, rgba(0,0,0,0.85), transparent)' }}>
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full" style={{ background: frame ? '#10B981' : 'var(--color-slate-gray)' }} />
              <span className="font-data-label px-2 py-0.5 rounded" style={{ color: '#fff', background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(255,255,255,0.15)', fontSize: '10px', letterSpacing: '0.08em' }}>
                {cameras.find(c => c.id === Number(selectedCameraId))?.name ?? 'No camera selected'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {/* Camera selector */}
              <select
                aria-label="Live camera"
                value={selectedCameraId || ''}
                onChange={handleCameraChange}
                disabled={cameras.length === 0}
                className="rounded px-2 py-0.5 text-white disabled:opacity-50"
                style={{ background: 'rgba(0,0,0,0.6)', border: '1px solid rgba(255,255,255,0.15)', fontSize: '11px', fontFamily: 'JetBrains Mono, monospace', backdropFilter: 'blur(4px)' }}
              >
                {cameras.length === 0
                  ? <option value="">{camerasLoaded ? 'No cameras configured' : 'Cameras not available'}</option>
                  : cameras.map((c) => <option key={c.id} value={c.id} disabled={!c.enabled}>{c.name}{c.enabled ? '' : ' — disabled'}</option>)
                }
              </select>
              {!isStreaming ? (
                <button onClick={() => startStream()} disabled={!selectedCameraId || health.state !== 'online' || cameras.length === 0}
                  className="px-3 py-0.5 rounded font-data-label uppercase tracking-wider transition-opacity hover:opacity-90 disabled:opacity-50"
                  style={{ background: '#FF6B00', color: '#000', fontSize: '10px', fontFamily: 'JetBrains Mono', fontWeight: 700 }}
                >▶ START</button>
              ) : (
                <button onClick={stopStream}
                  className="px-3 py-0.5 rounded font-data-label uppercase tracking-wider transition-opacity hover:opacity-90"
                  style={{ background: '#FF2D55', color: '#fff', fontSize: '10px', fontFamily: 'JetBrains Mono', fontWeight: 700 }}
                >■ STOP</button>
              )}
            </div>
          </div>

        </div>

      </section>

      {/* ── RIGHT: Widget Sidebar ─────────────────────────── */}
      <aside className="w-72 flex flex-col gap-2 p-4 h-full overflow-y-auto flex-shrink-0">

        {/* Site Compliance Gauge */}
        <Gauge
          label="Live Compliance"
          value={current?.compliance_rate ?? 'Not available'}
          color="#10B981"
          icon="verified_user"
        />

        <p className="font-data-label">Live compliance excludes workers with an unassessable mask and no other violation.</p>
        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-2">
          <StatTile label="MASK NOT ASSESSABLE" value={current?.mask_not_assessable ?? 'Not available'} />
          <StatTile label="WORKERS IN FRAME" value={current?.persons ?? 'Not available'} />
          <StatTile label="VIOLATIONS IN FRAME" value={current?.violations ?? 'Not available'} accent />
          <StatTile label="RECORDED TODAY (UTC)" value={history?.today_violations ?? 'Not available'} />
          <StatTile label="TOTAL RECORDED" value={history?.total_violations ?? 'Not available'} />
        </div>


        {/* Incident Log */}
        <div className="rounded flex flex-col overflow-hidden flex-1 min-h-0" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-outline-variant)' }}>
          <div className="px-3 py-2 flex justify-between items-center" style={{ background: 'var(--color-surface-container)', borderBottom: '1px solid var(--color-outline-variant)' }}>
            <h4 className="font-data-label" style={{ color: 'var(--color-on-surface-variant)' }}>INCIDENT LOG</h4>
            <span className="font-data-label px-2 py-0.5 rounded" style={{ background: 'var(--color-surface-container-high)', color: 'var(--color-on-surface-variant)', fontSize: '10px' }}>RECORDED</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {recentViolations.length > 0
              ? recentViolations.slice(0, 10).map((v, i) => (
                <IncidentItem
                  key={v.id ?? i}
                  violation={v} onAction={handleReview} busy={reviewBusy}
                />
              ))
              : (
                <p className="p-3 font-data-label">{history ? 'No recent violations' : 'Incident history not available'}</p>
              )
            }
          </div>
        </div>
      </aside>
      {health.reachable && <div className="w-full p-4"><Analytics /></div>}
    </div>
  );
};

export default DashboardPage;
