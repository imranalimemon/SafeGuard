import React, { useState, useRef } from 'react';
import { uploadImage, uploadVideo } from '../api/client';

const MODELS = [
  { value: 'yolov8s', label: 'YOLOv8s (Standard)' },
  { value: 'yolov8m', label: 'YOLOv8m (High Accuracy)' },
  { value: 'yolov8n', label: 'YOLOv8n (Fast)' },
];

const CLASSES = ['Personnel', 'PPE (Hardhat/Vest)', 'Vehicles', 'Restricted Zones'];

/* ── Detection result card ───────────────────────────────── */
const DetectionCard = ({ result, model }) => {
  if (!result) return null;
  // Backend payload for /upload/image is:
  //   { detections, violations, annotated_image_url,
  //     stats: { total_persons, compliant, violations, suppressed_by_cooldown } }
  // `inference_time_ms` and `model` are NOT returned — `model` comes from
  // the page's selected model state. Older code expected a different shape
  // (`persons_detected`, `inference_time_ms`) which made the card render
  // zeros and dashes forever.
  const violations = result.violations ?? [];
  const stats = result.stats ?? {};
  const persons = stats.total_persons ?? 0;
  const violating = stats.violations ?? violations.length;

  return (
    <div className="rounded p-4 flex flex-col gap-3 animate-slide-up" style={{ background: '#1c1f2a', border: '1px solid rgba(90,65,54,0.5)' }}>
      <div className="flex justify-between items-center">
        <h3 className="font-headline-sm" style={{ color: '#fff', fontSize: '15px' }}>Detection Results</h3>
        <span className="font-data-label px-2 py-0.5 rounded" style={{ background: '#FF6B00', color: '#000', fontSize: '10px', fontWeight: 700 }}>
          {model || 'YOLOv8s'}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: 'PERSONS', value: persons, color: '#44DCEA' },
          { label: 'VIOLATIONS', value: violating, color: violating > 0 ? '#FF2D55' : '#10B981' },
          // Inference time isn't tracked yet — render as `—` rather than a
          // bogus number from a missing field.
          { label: 'INFER TIME', value: '—', color: '#94A3B8' },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded p-3 text-center" style={{ background: '#262a35', border: '1px solid rgba(90,65,54,0.3)' }}>
            <div className="font-data-label mb-1" style={{ color: '#94A3B8', fontSize: '10px' }}>{label}</div>
            <div className="font-data-value" style={{ color, fontSize: '18px' }}>{value}</div>
          </div>
        ))}
      </div>
      {violations.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {violations.map((v, i) => (
            <div key={i} className="flex justify-between items-center px-3 py-2 rounded" style={{ background: 'rgba(255,45,85,0.08)', border: '1px solid rgba(255,45,85,0.2)' }}>
              <span className="font-data-label" style={{ color: '#FF2D55', fontSize: '11px' }}>
                {v.missing_ppe ? `Missing: ${v.missing_ppe.join(', ')}` : (v.violation_type || 'Violation')}
              </span>
              <span className="font-data-value" style={{ color: '#FF6B00', fontSize: '12px' }}>
                {v.confidence != null ? `${Math.round(v.confidence * 100)}%` : '—'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/* ── Queue Item ──────────────────────────────────────────── */
const QueueItem = ({ file, status }) => (
  <div className="flex items-center gap-3 px-3 py-2 rounded" style={{ background: '#1c1f2a', border: '1px solid rgba(90,65,54,0.3)' }}>
    <span className="material-symbols-outlined" style={{ fontSize: '18px', color: '#94A3B8' }}>
      {file.type.startsWith('video') ? 'videocam' : 'image'}
    </span>
    <div className="flex-1 min-w-0">
      <p className="font-data-value truncate" style={{ color: '#dfe2f1', fontSize: '12px' }}>{file.name}</p>
      <p className="font-data-label" style={{ color: '#94A3B8', fontSize: '10px' }}>{(file.size / 1024 / 1024).toFixed(1)} MB</p>
    </div>
    <span
      className="font-data-label px-2 py-0.5 rounded"
      style={{
        fontSize: '10px',
        background: status === 'done' ? 'rgba(16,185,129,0.15)' : status === 'error' ? 'rgba(255,45,85,0.15)' : 'rgba(255,107,0,0.15)',
        color: status === 'done' ? '#10B981' : status === 'error' ? '#FF2D55' : '#FF6B00',
        border: status === 'done' ? '1px solid rgba(16,185,129,0.3)' : status === 'error' ? '1px solid rgba(255,45,85,0.3)' : '1px solid rgba(255,107,0,0.3)',
      }}
    >
      {status === 'done' ? '✓ Done' : status === 'error' ? '✗ Error' : 'Processing…'}
    </span>
  </div>
);

/* ══════════════════════════════════════════════════════════ */
const UploadPage = () => {
  const [activeTab, setActiveTab]         = useState('image');
  const [isDragging, setIsDragging]       = useState(false);
  const [queue, setQueue]                 = useState([]);     // [{ file, status, result }]
  const [result, setResult]               = useState(null);
  const [isProcessing, setIsProcessing]   = useState(false);
  const [model, setModel]                 = useState('yolov8s');
  const [confidence, setConfidence]       = useState(70);
  const [classes, setClasses]             = useState({ Personnel: true, 'PPE (Hardhat/Vest)': true, Vehicles: true, 'Restricted Zones': false });
  const fileInputRef                      = useRef(null);

  /* ── file handling ──────────────────── */
  const handleFiles = async (files) => {
    const fileArr = Array.from(files);
    const accepted = fileArr.filter((f) => {
      if (activeTab === 'image') return f.type.startsWith('image/');
      return f.type.startsWith('video/');
    });
    if (!accepted.length) return;

    setQueue((q) => [...q, ...accepted.map((f) => ({ file: f, status: 'pending' }))]);
    setIsProcessing(true);

    for (const file of accepted) {
      try {
        const res = activeTab === 'image'
          ? await uploadImage(file)
          : await uploadVideo(file);
        setResult(res.data);
        setQueue((q) => q.map((item) => item.file === file ? { ...item, status: 'done', result: res.data } : item));
      } catch {
        setQueue((q) => q.map((item) => item.file === file ? { ...item, status: 'error' } : item));
      }
    }
    setIsProcessing(false);
  };

  const onDrop = (e) => { e.preventDefault(); setIsDragging(false); handleFiles(e.dataTransfer.files); };
  const onDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
  const onDragLeave = () => setIsDragging(false);
  const onFileSelect = (e) => { handleFiles(e.target.files); e.target.value = ''; };

  const toggleClass = (cls) => setClasses((c) => ({ ...c, [cls]: !c[cls] }));

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Page Header */}
      <div
        className="px-6 py-4 flex items-center justify-between flex-shrink-0 sticky top-0 z-10"
        style={{ background: 'rgba(10,14,24,0.8)', borderBottom: '1px solid rgba(90,65,54,0.3)', backdropFilter: 'blur(8px)' }}
      >
        <div>
          <h1 style={{ fontFamily: 'Geist, sans-serif', fontWeight: 700, fontSize: '28px', color: '#fff', letterSpacing: '-0.02em' }}>
            Upload &amp; Detect
          </h1>
          <p className="font-data-value mt-0.5" style={{ color: '#94A3B8', fontSize: '12px' }}>
            Process static media through selected inference models.
          </p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 rounded" style={{ background: '#1c1f2a', border: '1px solid rgba(90,65,54,0.5)' }}>
          <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: '#FF6B00' }} />
          <span className="font-data-value" style={{ color: '#dfe2f1', fontSize: '12px' }}>YOLOv8s Active</span>
        </div>
      </div>

      {/* Content Grid */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-7xl mx-auto">

          {/* Left: Upload Area (2/3) */}
          <div className="lg:col-span-2 flex flex-col gap-4">

            {/* Tabs */}
            <div className="flex items-center" style={{ borderBottom: '1px solid rgba(90,65,54,0.5)' }}>
              {[
                { id: 'image', label: 'Image Upload', icon: 'image' },
                { id: 'video', label: 'Video Upload', icon: 'videocam' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className="flex items-center gap-2 px-6 py-3 font-data-label uppercase tracking-wider transition-colors"
                  style={{
                    fontSize: '11px',
                    color: activeTab === tab.id ? '#FF6B00' : '#94A3B8',
                    borderBottom: activeTab === tab.id ? '2px solid #FF6B00' : '2px solid transparent',
                    background: activeTab === tab.id ? 'rgba(255,107,0,0.05)' : 'transparent',
                    fontWeight: activeTab === tab.id ? 700 : 500,
                  }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Drop Zone */}
            <div
              onDrop={onDrop}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className="relative rounded-lg flex flex-col items-center justify-center p-12 cursor-pointer group transition-all duration-200"
              style={{
                minHeight: '320px',
                border: `2px dashed ${isDragging ? '#FF6B00' : 'rgba(90,65,54,0.6)'}`,
                background: isDragging ? 'rgba(255,107,0,0.04)' : 'rgba(23,27,38,0.4)',
              }}
            >
              {/* Corner accents — appear on hover/drag */}
              {(['top-0 left-0 border-t-2 border-l-2', 'top-0 right-0 border-t-2 border-r-2', 'bottom-0 left-0 border-b-2 border-l-2', 'bottom-0 right-0 border-b-2 border-r-2']).map((cls, i) => (
                <div key={i} className={`absolute w-4 h-4 transition-opacity duration-200 ${cls} ${isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} style={{ borderColor: '#FF6B00' }} />
              ))}

              <div
                className="w-16 h-16 rounded-full flex items-center justify-center mb-5 transition-colors"
                style={{ background: isDragging ? 'rgba(255,107,0,0.2)' : '#313540' }}
              >
                <span className="material-symbols-outlined transition-colors" style={{ fontSize: '32px', color: isDragging ? '#FF6B00' : '#94A3B8' }}>
                  {isProcessing ? 'hourglass_top' : 'upload'}
                </span>
              </div>

              <h3 style={{ fontFamily: 'Geist, sans-serif', fontWeight: 700, fontSize: '20px', color: '#fff', marginBottom: '8px' }}>
                {isProcessing ? 'Processing…' : 'Drag & Drop media here'}
              </h3>
              <p className="font-data-value mb-8" style={{ color: '#94A3B8', fontSize: '12px' }}>
                Supported: {activeTab === 'image' ? 'JPG, PNG, WEBP' : 'MP4, AVI, MOV'} (Max 50MB)
              </p>
              <button
                type="button"
                className="px-8 py-3 rounded font-data-label uppercase tracking-wider transition-colors"
                style={{
                  background: '#FF6B00',
                  color: '#000',
                  fontSize: '11px',
                  fontWeight: 700,
                  boxShadow: '0 0 20px rgba(255,107,0,0.3)',
                }}
              >
                Select File
              </button>

              <input
                ref={fileInputRef}
                type="file"
                accept={activeTab === 'image' ? 'image/*' : 'video/*'}
                onChange={onFileSelect}
                multiple
                className="hidden"
              />
            </div>

            {/* Detection Result */}
            {result && <DetectionCard result={result} model={model} />}
          </div>

          {/* Right: Config + Queue (1/3) */}
          <div className="flex flex-col gap-4">

            {/* Processing Configuration */}
            <div className="rounded p-5" style={{ background: '#171b26', border: '1px solid rgba(90,65,54,0.5)' }}>
              <h3 className="font-data-label uppercase tracking-widest mb-4 pb-2" style={{ color: '#FF6B00', fontSize: '11px', borderBottom: '1px solid rgba(90,65,54,0.3)' }}>
                Processing Configuration
              </h3>
              <div className="flex flex-col gap-5">

                {/* Model */}
                <div>
                  <label className="block font-data-label uppercase mb-2" style={{ color: '#94A3B8', fontSize: '10px' }}>Inference Model</label>
                  <select
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="w-full rounded px-2 py-2 font-data-value outline-none"
                    style={{ background: '#0a0e18', border: '1px solid rgba(90,65,54,0.5)', color: '#dfe2f1', fontSize: '12px' }}
                  >
                    {MODELS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
                  </select>
                </div>

                {/* Confidence Slider */}
                <div>
                  <label className="block font-data-label uppercase mb-2" style={{ color: '#94A3B8', fontSize: '10px' }}>Confidence Threshold</label>
                  <div className="flex items-center gap-4">
                    <input
                      type="range" min={0} max={100} value={confidence}
                      onChange={(e) => setConfidence(Number(e.target.value))}
                      className="flex-1" style={{ accentColor: '#FF6B00' }}
                    />
                    <span className="font-data-value" style={{ color: '#fff', fontSize: '13px', minWidth: '36px' }}>{confidence}%</span>
                  </div>
                </div>

                {/* Detection Classes */}
                <div>
                  <label className="block font-data-label uppercase mb-2" style={{ color: '#94A3B8', fontSize: '10px' }}>Detection Classes</label>
                  <div className="flex flex-col gap-2">
                    {CLASSES.map((cls) => (
                      <label key={cls} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={classes[cls] ?? false}
                          onChange={() => toggleClass(cls)}
                          className="rounded"
                          style={{ accentColor: '#FF6B00' }}
                        />
                        <span className="font-data-value" style={{ color: '#dfe2f1', fontSize: '13px' }}>{cls}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Batch Queue */}
            <div className="rounded p-5 flex-1 flex flex-col" style={{ background: '#171b26', border: '1px solid rgba(90,65,54,0.5)' }}>
              <h3 className="font-data-label uppercase tracking-widest mb-4 pb-2" style={{ color: '#94A3B8', fontSize: '11px', borderBottom: '1px solid rgba(90,65,54,0.3)' }}>
                Batch Queue
              </h3>
              {queue.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center opacity-50">
                  <span className="material-symbols-outlined mb-2" style={{ fontSize: '32px', color: '#94A3B8' }}>folder_open</span>
                  <span className="font-data-label uppercase" style={{ color: '#94A3B8', fontSize: '10px' }}>Queue Empty</span>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {queue.map((item, i) => (
                    <QueueItem key={i} file={item.file} status={item.status} />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UploadPage;
