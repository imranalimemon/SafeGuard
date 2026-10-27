import React from 'react';

export function WorkerTable({ workers = [] }) {
  if (!workers.length) return <p>No workers found in this image/frame.</p>;
  return <table className="w-full text-left font-data-value" style={{ fontSize: '12px' }}>
    <thead><tr>{['Worker', 'Helmet', 'Safety Vest', 'Face Mask', 'Status'].map(label => <th key={label} className="p-2">{label}</th>)}</tr></thead>
    <tbody>{workers.map((worker, i) => <tr key={i}>
      <td className="p-2">W{worker.worker_id ?? i + 1}</td>
      {['Helmet', 'Safety Vest', 'Face Mask'].map(ppe => <td key={ppe} className="p-2">{worker.ppe_status?.[ppe] ?? 'not assessed'}</td>)}
      <td className="p-2">{worker.status === 'NOT_ASSESSABLE' ? 'Mask not assessable' : worker.status}</td>
    </tr>)}</tbody>
  </table>;
}

export default function UploadResult({ result, model }) {
  if (!result) return null;
  const video = result.media_type === 'video';
  return <section className="rounded p-4 flex flex-col gap-4" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-outline-variant)' }}>
    <h2 className="font-headline-sm">{video ? 'Video' : 'Image'} detection results</h2>
    {result.filename && <p>{result.filename}</p>}
    <p>{model || 'Model identity not available'}</p>
    {video ? <>
      <p>Frames decoded: {result.total_frames} · Frames analyzed: {result.frames_processed}</p>
      <p>Worker observations: {result.worker_observations} · Maximum workers in one frame: {result.max_workers_in_frame}</p>
      <p>Violating worker observations: {result.violations_detected} · Mask not assessable observations: {result.mask_not_assessable_observations}</p>
      <p>Workers are counted per analyzed frame, not as unique people across the video.</p>
      <h3>Annotated key frames (up to six)</h3>
      {(result.key_frames ?? []).map(frame => <figure key={frame.frame_number}>
        <figcaption>Frame {frame.frame_number}</figcaption>
        <img src={frame.screenshot_url} alt={`Annotated frame ${frame.frame_number}`} className="w-full object-contain" />
        <a href={frame.screenshot_url} download={`safeguard-frame-${frame.frame_number}.jpg`}>Download annotated frame</a>
        <WorkerTable workers={frame.workers} />
      </figure>)}
      <h3>Detected violations by analyzed frame</h3>
      {!(result.violation_frames ?? []).length && <p>No violations detected.</p>}
      {(result.violation_frames ?? []).map(frame => <div key={frame.frame_number}>
        <strong>Frame {frame.frame_number}</strong><WorkerTable workers={frame.violations} />
      </div>)}
    </> : <>
      <p>Workers found: {result.stats?.total_persons} · Violating workers: {result.stats?.violations}</p>
      <img src={result.annotated_image_url} alt="Annotated PPE result" className="w-full object-contain" />
      <a href={result.annotated_image_url} download="safeguard-annotated.jpg">Download annotated image</a>
      <WorkerTable workers={result.workers} />
    </>}
    <h3>Violations created: {(result.created_violations ?? []).length}</h3>
    <p>Suppressed by cooldown: {video ? result.suppressed_by_cooldown : result.stats?.suppressed_by_cooldown}</p>
    {!(result.created_violations ?? []).length && <p>No new violation records created.</p>}
    {(result.created_violations ?? []).map(row => <p key={row.id}>
      EV-{row.id}{row.frame_number ? ` · Frame ${row.frame_number}` : ''}: {row.violation_type} · {row.timestamp} UTC{' '}
      <a href={row.screenshot_path} target="_blank" rel="noreferrer">View evidence</a>
    </p>)}
  </section>;
}
