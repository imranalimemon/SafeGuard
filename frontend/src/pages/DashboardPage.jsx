import React, { useEffect, useState, useRef } from 'react';
import StatCard from '../components/ui/StatCard';
import { getDashboardStats } from '../api/client';

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

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
  }, []);

  const startStream = () => {
    if (!wsRef.current) {
      intentionallyStoppedRef.current = false;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsRef.current = new WebSocket(`${protocol}//${window.location.host}/ws/stream`);
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
            </div>
            <div className="flex gap-2">
              {!isStreaming ? (
                <button
                  onClick={startStream}
                  className="flex items-center gap-2 px-4 py-2 bg-sg-primary text-sg-on-primary font-body-md font-bold rounded hover:bg-sg-primary-fixed-dim transition-colors"
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
