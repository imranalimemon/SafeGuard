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
export const clearViolations = () => client.delete('/violations');

export default client;
