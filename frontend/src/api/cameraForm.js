export function cameraUpdatePayload(form) {
  // A blank, unexposed password field is not an instruction to erase credentials.
  const { password, ...fields } = form;
  return password ? { ...fields, password } : fields;
}

export function cameraErrorMessage(error, fallback = 'Camera request failed.') {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map(item => item.msg || 'Invalid camera value').join('; ');
  return typeof detail === 'string' ? detail : error?.message || fallback;
}
