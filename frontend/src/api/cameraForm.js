export function cameraUpdatePayload(form) {
  // A blank, unexposed password field is not an instruction to erase credentials.
  const { username, password, ...fields } = form;
  return { ...fields, ...(username && { username }), ...(password && { password }) };
}

export function cameraErrorMessage(error, fallback = 'Camera request failed.') {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map(item => item.msg || 'Invalid camera value').join('; ');
  return typeof detail === 'string' ? detail : error?.message || fallback;
}
