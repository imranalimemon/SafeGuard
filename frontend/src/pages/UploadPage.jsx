import React, { useState, useRef } from 'react';
import { uploadImage, uploadVideo } from '../api/client';

const UploadPage = () => {
  const [activeTab, setActiveTab] = useState('image');
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      setFile(f);
      setError(null);
      if (activeTab === 'image') {
        setPreview(URL.createObjectURL(f));
      } else {
        setPreview(f.name);
      }
      setResult(null);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const f = e.dataTransfer.files[0];
      setFile(f);
      setError(null);
      if (activeTab === 'image') {
        setPreview(URL.createObjectURL(f));
      } else {
        setPreview(f.name);
      }
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsProcessing(true);
    setError(null);
    try {
      let res;
      if (activeTab === 'image') {
        res = await uploadImage(file);
      } else {
        res = await uploadVideo(file);
      }
      setResult(res.data);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Detection failed. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const switchTab = (tab) => {
    setActiveTab(tab);
    handleReset();
  };

  const hasViolations = result && (
    (activeTab === 'image' && result.violations && result.violations.length > 0) ||
    (activeTab === 'video' && result.violations_detected > 0)
  );

  return (
    <div className="max-w-4xl mx-auto">
      {/* Tab switcher */}
      <div className="flex gap-6 mb-8 border-b border-sg-outline-variant">
        <button
          onClick={() => switchTab('image')}
          className={`flex items-center gap-2 pb-3 px-2 border-b-2 transition-colors font-body-md font-medium ${
            activeTab === 'image' ? 'border-sg-primary text-sg-primary' : 'border-transparent text-sg-on-surface-variant hover:text-sg-on-surface'
          }`}
        >
          <span className="material-symbols-outlined text-xl">image</span>
          <span>Image Upload</span>
        </button>
        <button
          onClick={() => switchTab('video')}
          className={`flex items-center gap-2 pb-3 px-2 border-b-2 transition-colors font-body-md font-medium ${
            activeTab === 'video' ? 'border-sg-primary text-sg-primary' : 'border-transparent text-sg-on-surface-variant hover:text-sg-on-surface'
          }`}
        >
          <span className="material-symbols-outlined text-xl">videocam</span>
          <span>Video Upload</span>
        </button>
      </div>

      {/* Upload area */}
      <div
        className="bg-sg-surface border border-sg-outline-variant border-dashed rounded-xl p-10 mb-6 text-center"
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
      >
        {!file ? (
          <div className="flex flex-col items-center">
            <div className="w-16 h-16 bg-sg-surface-container rounded-full flex items-center justify-center mb-4 border border-sg-outline-variant">
              <span className="material-symbols-outlined text-3xl text-sg-primary">upload</span>
            </div>
            <h3 className="font-headline-sm text-sg-on-surface mb-2">Drag & Drop your {activeTab} here</h3>
            <p className="font-body-md text-sg-on-surface-variant mb-6">or click to browse from your computer</p>
            <input
              ref={fileInputRef}
              type="file"
              id="file-upload"
              className="hidden"
              accept={activeTab === 'image' ? "image/*" : "video/*"}
              onChange={handleFileChange}
            />
            <label
              htmlFor="file-upload"
              className="bg-sg-primary text-sg-on-primary px-6 py-2.5 rounded-lg cursor-pointer transition-colors font-body-md font-bold hover:bg-sg-primary-fixed-dim shadow-[0_0_15px_rgba(255,182,147,0.15)]"
            >
              Select File
            </label>
          </div>
        ) : (
          <div className="flex flex-col items-center">
            {/* Show annotated image if result, otherwise preview */}
            {activeTab === 'image' && (
              <img
                src={result?.annotated_image_url || preview}
                alt="Preview"
                className="max-h-80 rounded-lg border border-sg-outline-variant mb-6 object-contain"
              />
            )}
            {activeTab === 'video' && (
              <div className="mb-6 p-6 bg-sg-surface-container rounded-lg border border-sg-outline-variant">
                <span className="material-symbols-outlined text-3xl text-sg-primary mb-2 block">videocam</span>
                <p className="font-body-lg text-sg-on-surface font-medium">{file?.name}</p>
                <p className="font-body-md text-sg-on-surface-variant">{(file?.size / (1024 * 1024)).toFixed(1)} MB</p>
              </div>
            )}

            {/* Error message */}
            {error && (
              <div className="flex items-center gap-2 text-sg-error mb-4 bg-sg-error-container/20 px-4 py-2 rounded-lg border border-sg-error/30">
                <span className="material-symbols-outlined text-lg">warning</span>
                <span className="font-body-md">{error}</span>
              </div>
            )}

            {!result ? (
              <div className="flex gap-3">
                <button
                  onClick={handleUpload}
                  disabled={isProcessing}
                  className={`px-8 py-3 rounded-lg font-body-md font-bold transition-colors flex items-center gap-2 ${
                    isProcessing
                      ? 'bg-sg-primary/50 text-sg-on-primary cursor-not-allowed'
                      : 'bg-sg-primary text-sg-on-primary hover:bg-sg-primary-fixed-dim shadow-[0_0_15px_rgba(255,182,147,0.15)]'
                  }`}
                >
                  {isProcessing ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                      <span>Processing...</span>
                    </>
                  ) : (
                    <>
                      <span className="material-symbols-outlined text-sm">search</span>
                      <span>Run Detection</span>
                    </>
                  )}
                </button>
                <button
                  onClick={handleReset}
                  className="px-4 py-3 rounded-lg border border-sg-outline-variant hover:bg-sg-surface-container-high transition-colors font-body-md text-sg-on-surface"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <div className="flex gap-3">
                <button
                  onClick={handleReset}
                  className="flex items-center gap-2 bg-sg-primary text-sg-on-primary px-6 py-2.5 rounded-lg transition-colors font-body-md font-bold hover:bg-sg-primary-fixed-dim"
                >
                  <span className="material-symbols-outlined text-sm">refresh</span>
                  <span>Upload Another</span>
                </button>
                {result.annotated_image_url && (
                  <a
                    href={result.annotated_image_url}
                    download="safeguard_detection.jpg"
                    className="flex items-center gap-2 bg-transparent border border-sg-outline-variant hover:bg-sg-surface-container-high px-6 py-2.5 rounded-lg transition-colors font-body-md text-sg-on-surface"
                  >
                    <span className="material-symbols-outlined text-sm">download</span>
                    <span>Download Result</span>
                  </a>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Image Results */}
      {result && activeTab === 'image' && (
        <div className="space-y-4 animate-stagger-1">
          {/* Stats cards */}
          <div className="grid grid-cols-3 gap-4">
            <div className={`border rounded-xl p-5 flex flex-col items-center justify-center ${hasViolations ? 'bg-sg-error-container/10 border-sg-error/20' : 'bg-sg-tertiary-container/10 border-sg-tertiary/20'}`}>
              <span className={`text-3xl font-mono font-bold mb-1 ${hasViolations ? 'text-sg-error' : 'text-sg-tertiary'}`}>
                {result.stats?.violations || 0}
              </span>
              <span className="font-body-md text-sg-on-surface-variant">Violations</span>
            </div>
            <div className="bg-sg-surface border border-sg-outline-variant rounded-xl p-5 flex flex-col items-center justify-center">
              <span className="text-3xl font-mono text-sg-primary font-bold mb-1">{result.stats?.total_persons || 0}</span>
              <span className="font-body-md text-sg-on-surface-variant">Persons Found</span>
            </div>
            <div className="bg-sg-surface border border-sg-outline-variant rounded-xl p-5 flex flex-col items-center justify-center">
              <span className="text-3xl font-mono text-sg-tertiary font-bold mb-1">{result.detections?.length || 0}</span>
              <span className="font-body-md text-sg-on-surface-variant">Objects Detected</span>
            </div>
          </div>

          {/* Detections table */}
          {result.detections && result.detections.length > 0 && (
            <div className="bg-sg-surface-container border border-sg-outline-variant rounded-xl overflow-hidden">
              <div className="px-5 py-4 border-b border-sg-outline-variant bg-sg-surface-container-low">
                <h3 className="font-headline-sm text-sg-on-surface">Detection Details</h3>
              </div>
              <div className="grid grid-cols-3 gap-4 px-5 py-3 border-b border-sg-outline-variant bg-sg-surface-container/50">
                <div className="font-label-caps text-sg-on-surface-variant">Class</div>
                <div className="font-label-caps text-sg-on-surface-variant">Confidence</div>
                <div className="font-label-caps text-sg-on-surface-variant">Bounding Box</div>
              </div>
              {result.detections.map((d, i) => (
                <div key={i} className="grid grid-cols-3 gap-4 px-5 py-3 border-b border-sg-outline-variant/50 items-center hover:bg-sg-surface-variant transition-colors">
                  <div>
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      d.class_name === 'Person' ? 'bg-sg-primary/10 text-sg-primary border border-sg-primary/20' :
                      d.class_name === 'Helmet' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                      d.class_name === 'Safety Vest' ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20' :
                      'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                    }`}>
                      {d.class_name}
                    </span>
                  </div>
                  <div className="font-data-mono text-sg-on-surface">{(d.confidence * 100).toFixed(1)}%</div>
                  <div className="font-data-mono text-sg-on-surface-variant text-sm">[{d.bbox?.join(', ')}]</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Video Results */}
      {result && activeTab === 'video' && (
        <div className="grid grid-cols-3 gap-4 animate-stagger-1">
          <div className={`border rounded-xl p-5 flex flex-col items-center justify-center ${hasViolations ? 'bg-sg-error-container/10 border-sg-error/20' : 'bg-sg-tertiary-container/10 border-sg-tertiary/20'}`}>
            <span className={`text-3xl font-mono font-bold mb-1 ${hasViolations ? 'text-sg-error' : 'text-sg-tertiary'}`}>
              {result.violations_detected || 0}
            </span>
            <span className="font-body-md text-sg-on-surface-variant">Violations Detected</span>
          </div>
          <div className="bg-sg-surface border border-sg-outline-variant rounded-xl p-5 flex flex-col items-center justify-center">
            <span className="text-3xl font-mono text-sg-primary font-bold mb-1">{result.total_frames || 0}</span>
            <span className="font-body-md text-sg-on-surface-variant">Total Frames</span>
          </div>
          <div className="bg-sg-surface border border-sg-outline-variant rounded-xl p-5 flex flex-col items-center justify-center">
            <span className="text-3xl font-mono text-sg-tertiary font-bold mb-1">{result.violation_frames?.length || 0}</span>
            <span className="font-body-md text-sg-on-surface-variant">Violation Frames</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadPage;
