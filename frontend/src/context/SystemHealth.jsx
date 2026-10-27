import React, { createContext, useContext, useEffect, useState } from 'react';
import { getHealth } from '../api/client';

const initialHealth = { state: 'checking', reachable: false, model_loaded: false, db_connected: false };
export const SystemHealthContext = createContext(initialHealth);

export const SystemHealthProvider = ({ children }) => {
  const [health, setHealth] = useState(initialHealth);

  useEffect(() => {
    let cancelled = false;
    let timer;
    const controller = new AbortController();
    const check = async () => {
      try {
        const { data } = await getHealth({ signal: controller.signal });
        if (typeof data?.model_loaded !== 'boolean' || typeof data?.db_connected !== 'boolean') {
          throw new Error('Invalid backend health response');
        }
        if (!cancelled) setHealth({
          ...data, reachable: true,
          state: data.model_loaded && data.db_connected ? 'online' : 'degraded',
        });
      } catch {
        if (!cancelled) setHealth({ ...initialHealth, state: 'offline' });
      } finally {
        if (!cancelled) timer = setTimeout(check, 5000);
      }
    };
    check();
    return () => { cancelled = true; clearTimeout(timer); controller.abort(); };
  }, []);

  return <SystemHealthContext.Provider value={health}>{children}</SystemHealthContext.Provider>;
};

export const useSystemHealth = () => {
  const health = useContext(SystemHealthContext);
  const labels = { checking: 'Checking', online: 'Online', degraded: 'Degraded', offline: 'Offline' };
  const colors = { checking: '#64748b', online: '#10B981', degraded: '#FF6B00', offline: '#FF2D55' };
  return { ...health, label: labels[health.state], color: colors[health.state] };
};
