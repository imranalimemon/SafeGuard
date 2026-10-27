export function validateUpload(file, kind, limits) {
  const policy = limits?.[kind];
  if (!policy) return 'Upload limits are not available. Retry when the backend is reachable.';
  const extension = `.${file.name.split('.').at(-1).toLowerCase()}`;
  if (!policy.extensions.includes(extension)) return `Allowed ${kind} types: ${policy.extensions.join(', ')}`;
  if (!file.size) return 'The file is empty.';
  if (file.size > policy.max_bytes) return `File exceeds the ${policy.max_bytes / (1024 * 1024)} MiB ${kind} limit.`;
  return null;
}

export function validUploadLimits(limits) {
  return ['image', 'video'].every(kind => Number.isInteger(limits?.[kind]?.max_bytes)
    && limits[kind].max_bytes > 0 && Array.isArray(limits[kind].extensions) && limits[kind].extensions.length > 0);
}

export function uploadError(error) {
  const detail = error.response?.data?.detail || error.response?.data?.error;
  if (Array.isArray(detail)) return detail.map(item => item.msg).join('; ');
  return detail || error.message || 'Upload failed. Check the backend connection.';
}

export function uploadPhase(status, progress) {
  if (status === 'done') return 'Done';
  if (status === 'error') return 'Error';
  if (status === 'pending') return 'Queued';
  if (status === 'uploading') return progress == null ? 'Uploading…' : `Uploading ${progress}%`;
  return 'Processing on backend…';
}
