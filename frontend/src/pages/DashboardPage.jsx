import React, { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { getDashboardStats, listCameras } from '../api/client';
import { useSystemHealth } from '../context/SystemHealth';
import { createLiveStream } from '../api/liveStream';

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
        style={{ color: accent ? '#FF2D55' : 'var(--color-on-surface)', fontSize: '22px', fontFamily: 'Geist, sans-serif', fontWeight: 600, ...(accent ? { animation: 'pulse 2s infinite' } : {}) }}
      >
        {value}
      </div>
    </div>
  </div>
);

const IncidentItem = ({ type, camera, confidence, time, severity = 'critical', resolved = false }) => {
  const borderColor = severity === 'critical' ? '#FF2D55' : severity === 'warn' ? '#FF6B00' : 'var(--color-outline)';
  const typeColor   = severity === 'critical' ? '#FF2D55' : severity === 'warn' ? '#FF6B00' : 'var(--color-on-surface-variant)';
  return (
    <div
      className="p-3 cursor-pointer transition-colors"
      style={{
        borderBottom: '1px solid var(--color-outline-variant)',
        borderLeft: `2px solid ${borderColor}`,
        background: resolved ? 'transparent' : severity === 'critical' ? 'rgba(255,45,85,0.05)' : 'transparent',
        opacity: resolved ? 0.55 : 1,
      }}
    >
      <div className="flex justify-between items-start mb-1">
        <span className="font-data-label font-bold" style={{ color: typeColor }}>{type}</span>
        <span className="font-data-value" style={{ color: 'var(--color-on-surface-variant)', fontSize: '10px' }}>{time}</span>
      </div>
      <div style={{ fontSize: '12px', color: 'var(--color-on-surface-variant)', marginBottom: resolved || severity === 'warn' ? 0 : '8px' }}>
        {camera}{confidence != null ? ` · CONF ${confidence}%` : ''}
        {resolved ? ' · RESOLVED' : ''}
      </div>
      {!resolved && severity === 'critical' && (
        <div className="flex gap-2">
          <button
            disabled
            title="Acknowledge — Coming soon"
            className="font-data-label uppercase tracking-wider px-2 py-1 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ fontSize: '10px', background: 'var(--color-surface-container-high)', border: '1px solid var(--color-outline-variant)', color: 'var(--color-on-surface)' }}
          >
            Acknowledge — Coming soon
          </button>
          <button
            disabled
            title="Escalate — Coming soon"
            className="font-data-label uppercase tracking-wider px-2 py-1 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ fontSize: '10px', background: 'transparent', border: '1px solid rgba(255,45,85,0.4)', color: '#FF2D55' }}
          >
            Escalate — Coming soon
          </button>
        </div>
      )}
    </div>
  );
};


const DashboardPage = () => {
  const health = useSystemHealth();
  const [isStreaming, setIsStreaming] = useState(false);
  const [frame, setFrame] = useState(null);
  const [frameKey, setFrameKey] = useState(null);
  const [liveStats, setLiveStats] = useState(null);
  const [stats, setStats] = useState(null);
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
    <div className="flex h-full overflow-hidden">

      {/* One selected, configured camera; no placeholder camera slots. */}
      <section className="flex-1 flex flex-col gap-2 p-4 h-full overflow-hidden">
        {health.state === 'offline' && <p role="status">Backend offline. Live data is not available.</p>}
        {health.state === 'degraded' && <p role="status">Backend reachable, but {!health.model_loaded ? 'model is unavailable' : 'database is unavailable'}.</p>}
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

          {/* PTZ hover controls */}
          <div className="absolute bottom-3 right-3 glass-panel rounded p-1.5 flex gap-1.5 z-30 opacity-0 group-hover:opacity-100 transition-opacity">
            {['zoom_in', 'zoom_out', 'crop_free'].map((icon) => (
              <button key={icon} disabled title="PTZ — Coming soon" aria-label={`${icon} — Coming soon`} className="p-1 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed" style={{ color: '#fff' }}>
                <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>{icon}</span>
              </button>
            ))}
            <span className="font-data-label text-white" style={{ fontSize: '10px' }}>Coming soon</span>
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

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-2">
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
                  type={(v.violation_type || 'UNKNOWN').toUpperCase()}
                  camera={v.source ?? 'Source not available'}
                  confidence={v.confidence != null ? Math.round(v.confidence * 100) : null}
                  time={new Date(v.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                />
              ))
              : (
                <p className="p-3 font-data-label">{history ? 'No recent violations' : 'Incident history not available'}</p>
              )
            }
          </div>
        </div>
      </aside>
    </div>
  );
};

export default DashboardPage;
