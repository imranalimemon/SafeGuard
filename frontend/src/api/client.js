import axios from 'axios';

const client = axios.create({
  baseURL: '/api',
});

export const getHealth = () => client.get('/health');
export const getDashboardStats = () => client.get('/stats/dashboard');
export const getViolations = (params) => client.get('/violations', { params });
export const getViolationById = (id) => client.get(`/violations/${id}`);
export const uploadImage = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return client.post('/upload/image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const uploadVideo = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return client.post('/upload/video', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const getAlertSettings = () => client.get('/settings/alerts');
export const updateAlertSettings = (data) => client.put('/settings/alerts', data);
// Fire a single test alert through the same code path as a real violation.
// `transport` in the response will be 'smtp' / 'twilio' / 'debug' — the
// UI surfaces that so the operator knows whether they're seeing real
// delivery or local receiver output.
export const sendTestEmail = () => client.post('/settings/alerts/test-email');
export const sendTestWhatsApp = () => client.post('/settings/alerts/test-whatsapp');
export const clearViolations = () => client.delete('/violations');

// Cameras CRUD — see backend/api/cameras.py. Errors propagate via the axios
// instance's normal reject path (caller renders the message).
export const listCameras = () => client.get('/cameras');
export const createCamera = (data) => client.post('/cameras', data);
export const updateCamera = (id, data) => client.put(`/cameras/${id}`, data);
export const deleteCamera = (id) => client.delete(`/cameras/${id}`);
export const testCamera = (id) => client.post(`/cameras/${id}/test`);
// Enumerate local webcam indices — backend probes 0..max_index-1 and returns
// the ones that actually produce a frame on this machine.
export const scanCameras = (maxIndex = 4) =>
  client.get('/cameras/scan-local', { params: { max_index: maxIndex } });

export default client;
