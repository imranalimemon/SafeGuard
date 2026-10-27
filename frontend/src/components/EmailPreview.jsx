import React, { useState } from 'react';

export function EmailPreview({ preview }) {
  return <section className="p-3 rounded" style={{ background: 'var(--color-surface-container)', overflowWrap: 'anywhere' }}>
    <p role="status">Preview only. Nothing was sent.</p>
    <p><strong>To:</strong> {preview.to || 'Recipient not configured'}</p>
    <p><strong>Subject:</strong> {preview.subject}</p>
    <pre style={{ whiteSpace: 'pre-wrap', fontSize: '12px' }}>{preview.body}</pre>
    <p>Attachments: {preview.attachments.map(a => `${a.filename} (${a.bytes} bytes)`).join(', ') || 'None (manual settings test)'}</p>
    <a href={`data:message/rfc822;base64,${preview.eml_base64}`} download="safeguard-email-preview.eml">Download exact email (.eml)</a>
  </section>;
}

export default function EmailPreviewButton({ load }) {
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const show = async () => {
    setBusy(true); setError(null); setPreview(null);
    try { setPreview((await load()).data); }
    catch (err) { setError(err.response?.data?.detail || err.message || 'Preview failed'); }
    finally { setBusy(false); }
  };
  return <div>
    <button disabled={busy} onClick={show}>{busy ? 'Building preview…' : 'Preview email'}</button>
    {error && <p role="alert">{error}</p>}
    {preview && <EmailPreview preview={preview} />}
  </div>;
}
