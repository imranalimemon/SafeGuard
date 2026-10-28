import React from 'react';
import { useSystemHealth } from '../../context/SystemHealth';

const Footer = () => {
  const health = useSystemHealth();
  return (
  <footer
    className="fixed bottom-0 left-64 right-0 h-8 z-40 flex items-center justify-between px-6"
    style={{
      background: 'var(--color-surface)',
      borderTop: '1px solid var(--color-outline-variant)',
    }}
  >
    <div className="font-data-value flex items-center gap-4" style={{ color: 'var(--color-on-surface)', fontSize: '11px' }}>
      System Status: <span style={{ color: health.color }}>{health.label}</span>
      &nbsp;|&nbsp;Model: {health.model_name ?? 'Not available'}
      &nbsp;|&nbsp;Provider: {health.execution_providers?.join(', ') || 'Not available'}
    </div>
  </footer>
);
};

export default Footer;
