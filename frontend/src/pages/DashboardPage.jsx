import React, { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import StatCard from '../components/ui/StatCard';
import { getDashboardStats, listCameras } from '../api/client';

const SELECTED_CAMERA_KEY = 'sg_selected_camera';

const DashboardPage = () => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [frame, setFrame] = useState(null);
  const [stats, setStats] = useState({
    total_violations: 0,
    today_violations: 0,
    total_persons_detected: 0,
    compliance_rate: 0,
    avg_confidence: 0,
    recent_violations: []
  });
  const [cameras, setCameras] = useState([]);
  const [selectedCameraId, setSelectedCameraId] = useState(
    () => localStorage.getItem(SELECTED_CAMERA_KEY) || null
  );
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const intentionallyStoppedRef = useRef(false);

  const fetchStats = async () => {
    try {
      const res = await getDashboardStats();
      setStats(res.data);
    } catch (error) {
      console.error("Failed to fetch dashboard stats", error);
    }
  };

  const fetchCameras = async () => {
    try {
      const res = await listCameras();
      const data = Array.isArray(res.data) ? res.data : [];
      setCameras(data);
      // If the persisted camera is gone — deleted, disabled, or never set —
      // fall back to the first available enabled camera.
      setSelectedCameraId((current) => {
        if (current && data.find((c) => c.id === Number(current) && c.enabled)) {
          return current;
        }
        const first = data.find((c) => c.enabled);
        const next = first ? String(first.id) : null;
        if (next) localStorage.setItem(SELECTED_CAMERA_KEY, next);
        return next;
      });
    } catch (err) {
      console.error("Failed to load cameras", err);
      setCameras([]);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    fetchCameras();
  }, []);

  const handleCameraChange = (e) => {
    const id = e.target.value || null;
    setSelectedCameraId(id);
    if (id) localStorage.setItem(SELECTED_CAMERA_KEY, id);
    // If the stream is up, restart it against the new camera.
    if (isStreaming) {
      intentionallyStoppedRef.current = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setIsStreaming(false);
      setFrame(null);
      // Defer slightly so the onclose cleanup runs first.
      setTimeout(() => startStream(), 50);
    }
  };

  const startStream = () => {
    if (!wsRef.current) {
      if (!selectedCameraId) {
        // No camera selected — nothing to connect to.
        return;
      }
      intentionallyStoppedRef.current = false;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsRef.current = new WebSocket(
        `${protocol}//${window.location.host}/ws/stream/${selectedCameraId}`
      );
      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.frame) {
            setFrame(`data:image/jpeg;base64,${data.frame}`);
          }
        } catch (e) {
          setFrame(`data:image/jpeg;base64,${event.data}`);
        }
      };
      wsRef.current.onclose = () => {
        wsRef.current = null;
        if (!intentionallyStoppedRef.current) {
          reconnectTimeoutRef.current = setTimeout(startStream, 3000);
        } else {
          setIsStreaming(false);
        }
      };
      setIsStreaming(true);
    }
  };

  const stopStream = () => {
    intentionallyStoppedRef.current = true;
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsStreaming(false);
    setFrame(null);
  };

  useEffect(() => {
    return () => {
      intentionallyStoppedRef.current = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  return (
    <div className="flex flex-col gap-4">
      {/* Top Row: Live Feed + Right KPIs */}
      <div className="grid grid-cols-12 gap-4" style={{ height: '700px' }}>
        {/* Live Feed Card */}
        <div className="bg-sg-surface border border-sg-outline-variant rounded-xl flex flex-col animate-stagger-1 overflow-hidden col-span-9">
          <div className="px-5 py-4 border-b border-sg-outline-variant flex justify-between items-center bg-sg-surface-container-low">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-sg-on-surface-variant">videocam</span>
              <h2 className="font-headline-sm text-sg-on-surface">Live Feed</h2>
              <div className="relative ml-3">
                <select
                  value={selectedCameraId || ''}
                  onChange={handleCameraChange}
                  disabled={cameras.length === 0}
                  className="appearance-none bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-body-md rounded-lg pl-4 pr-10 py-1.5 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {cameras.length === 0 ? (
                    <option value="">No cameras</option>
                  ) : (
                    cameras.map((c) => (
                      <option key={c.id} value={c.id} disabled={!c.enabled}>
                        {c.name}{c.source_type ? ` (${c.source_type})` : ''}{c.enabled ? '' : ' — disabled'}
                      </option>
                    ))
                  )}
                </select>
                <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-sg-on-surface-variant pointer-events-none text-sm">expand_more</span>
              </div>
              {cameras.length === 0 && (
                <Link
                  to="/cameras"
                  className="ml-3 font-body-md text-sg-primary hover:text-sg-primary-fixed-dim transition-colors"
                >
                  Add a camera →
                </Link>
              )}
            </div>
            <div className="flex gap-2">
              {!isStreaming ? (
                <button
                  onClick={startStream}
                  disabled={!selectedCameraId || cameras.length === 0}
                  className="flex items-center gap-2 px-4 py-2 bg-sg-primary text-sg-on-primary font-body-md font-bold rounded hover:bg-sg-primary-fixed-dim transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span className="material-symbols-outlined text-sm">play_arrow</span>
                  Start Stream
                </button>
              ) : (
                <button
                  onClick={stopStream}
                  className="flex items-center gap-2 px-4 py-2 bg-sg-error-container text-sg-on-error-container font-body-md font-bold rounded hover:opacity-90 transition-colors"
                >
                  <span className="material-symbols-outlined text-sm">stop</span>
                  Stop Stream
                </button>
              )}
            </div>
          </div>
          <div className="flex-1 flex flex-col items-center justify-center bg-[#05080f] relative">
            {isStreaming && frame ? (
              <img src={frame} alt="Live feed" className="w-full h-full object-contain transition-opacity duration-200" />
            ) : (
              <>
                <span className="material-symbols-outlined text-5xl text-sg-surface-bright mb-4">videocam_off</span>
                <p className="font-body-lg text-sg-on-surface-variant mb-1">No camera connected</p>
                <p className="font-body-md text-sg-surface-bright">Click 'Start Stream' to connect</p>
              </>
            )}
            {isStreaming && (
              <div className="absolute top-4 left-4 flex items-center gap-2 bg-black/60 px-3 py-1.5 rounded-full backdrop-blur-sm border border-white/10">
                <div className="w-2 h-2 rounded-full bg-sg-error animate-pulse"></div>
                <span className="font-data-mono text-white">LIVE</span>
              </div>
            )}
          </div>
        </div>

        {/* Right Column KPIs */}
        <div className="grid gap-4 col-span-3 grid-cols-1">
          <StatCard
            icon="gpp_bad"
            label="Total Violations Today"
            value={stats.today_violations}
            iconBg="bg-sg-error-container/20"
            iconBorder="border-sg-error-container/30"
            iconColor="text-sg-error"
            animClass="animate-stagger-2 animate-pulse-kpi"
          />
          <StatCard
            icon="groups"
            label="Workers Detected"
            value={stats.total_persons_detected}
            iconBg="bg-sg-surface-container-high"
            iconBorder="border-sg-outline-variant"
            iconColor="text-sg-primary"
            animClass="animate-stagger-3"
          />
          <StatCard
            icon="monitoring"
            label="Compliance Rate"
            value={`${stats.compliance_rate}%`}
            iconBg="bg-sg-tertiary-container/10"
            iconBorder="border-sg-tertiary-container/20"
            iconColor="text-sg-tertiary"
            animClass="animate-stagger-4"
          />
          <StatCard
            icon="center_focus_strong"
            label="Model Accuracy"
            value={`${stats.avg_confidence}%`}
            iconBg="bg-sg-surface-container-high"
            iconBorder="border-sg-outline-variant"
            iconColor="text-sg-on-surface"
            animClass="animate-stagger-5"
          />
        </div>
      </div>

      {/* Recent Violations Section */}
      <div className="bg-sg-surface border border-sg-outline-variant rounded-xl animate-stagger-5 mt-4 overflow-hidden">
        <div className="px-5 py-4 border-b border-sg-outline-variant bg-sg-surface-container-low">
          <h2 className="font-headline-sm text-sg-on-surface">Recent Violations</h2>
        </div>
        {/* Table Header */}
        <div className="grid grid-cols-4 gap-4 px-5 py-3 border-b border-sg-outline-variant bg-sg-surface-container/50">
          <div className="font-label-caps text-sg-on-surface-variant">Time</div>
          <div className="font-label-caps text-sg-on-surface-variant">Type</div>
          <div className="font-label-caps text-sg-on-surface-variant">Confidence</div>
          <div className="font-label-caps text-sg-on-surface-variant text-right">Action</div>
        </div>
        {/* Table Rows */}
        <div className="divide-y divide-sg-outline-variant">
          {stats.recent_violations && stats.recent_violations.length > 0 ? (
            stats.recent_violations.map((v) => (
              <div key={v.id} className="grid grid-cols-4 gap-4 px-5 py-3 items-center hover:bg-sg-surface-container-high transition-colors">
                <div className="font-data-mono text-sg-on-surface">
                  {new Date(v.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-sg-error"></span>
                  <span className="font-body-md text-sg-on-surface">{v.violation_type || 'Unknown'}</span>
                </div>
                <div className="font-data-mono text-sg-on-surface-variant">{Math.round((v.confidence || 0) * 100)}%</div>
                <div className="text-right">
                  <a href="/violations" className="font-body-md text-sg-primary hover:text-sg-primary-fixed-dim transition-colors">View</a>
                </div>
              </div>
            ))
          ) : (
            <div className="px-5 py-8 text-center">
              <p className="font-body-md text-sg-on-surface-variant">No recent violations detected.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
