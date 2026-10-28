import React, { useEffect, useState } from 'react';
import client from '../api/client';

export default function SystemLogsPage() {
  const [lines, setLines] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = async signal => {
    setBusy(true);
    try {
      const { data } = await client.get('/system/logs', { signal });
      if (!signal?.aborted) { setLines(data.lines); setError(null); }
    } catch (e) { if (!signal?.aborted) setError(e.response?.data?.detail || 'System logs unavailable. Retry when the backend is reachable.'); }
    finally { if (!signal?.aborted) setBusy(false); }
  };
  useEffect(() => { const controller = new AbortController(); load(controller.signal); return () => controller.abort(); }, []);
  return <section className="p-6 overflow-auto" style={{ minHeight: 0 }}>
    <h1 className="text-2xl font-bold">System Logs</h1>
    <p>Recent operational log lines in UTC. Logs rotate on disk; this view shows the latest file.</p>
    <button className="px-4 py-2 my-3 border rounded" disabled={busy} onClick={() => load()}>{busy ? 'Loading...' : 'Refresh logs'}</button>
    {error && <p role="alert">{error}</p>}
    {lines?.length === 0 && <p>No operational log lines have been recorded.</p>}
    {lines?.length > 0 && <pre tabIndex={0} aria-label="Operational log lines" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', fontSize: 12 }}>{lines.join('\n')}</pre>}
  </section>;
}
