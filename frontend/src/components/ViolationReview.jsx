import React from 'react';

export function ReviewState({ violation }) {
  return <div className="font-data-label" style={{ fontSize: '11px' }}>
    <strong>{violation.review_status || 'open'}</strong>
    {violation.acknowledged_at && <div>Acknowledged: {violation.acknowledged_at} UTC</div>}
    {violation.escalated_at && <div>Escalated: {violation.escalated_at} UTC</div>}
    {violation.archived_at && <div>Archived: {violation.archived_at} UTC</div>}
    {violation.mask_assessment && <div>Mask: {violation.mask_assessment}</div>}
  </div>;
}

export function ReviewActions({ violation, onAction, busy = false }) {
  return <div className="flex gap-2 flex-wrap" onClick={e => e.stopPropagation()}>
    {!violation.acknowledged_at && <button disabled={busy} onClick={() => onAction(violation.id, 'acknowledge')}>Acknowledge</button>}
    {violation.review_status !== 'escalated' && <button disabled={busy} onClick={() => onAction(violation.id, 'escalate')}>Escalate</button>}
    {!violation.archived_at && <button disabled={busy} onClick={() => onAction(violation.id, 'archive')}>Archive Evidence</button>}
  </div>;
}
