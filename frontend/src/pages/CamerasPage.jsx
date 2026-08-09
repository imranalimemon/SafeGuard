import React, { useState, useEffect, useCallback } from 'react';
import {
  listCameras,
  createCamera,
  updateCamera,
  deleteCamera,
  testCamera,
} from '../api/client';
import Drawer from '../components/ui/Drawer';
import Toggle from '../components/ui/Toggle';

// Source-type badge colors — same palette used in ViolationsPage source chips.
const SOURCE_TYPE_STYLES = {
  ip: 'bg-sg-primary-container/20 text-sg-primary border-sg-primary/30',
  rtsp: 'bg-sg-secondary-container/20 text-sg-secondary border-sg-secondary/30',
  webcam: 'bg-sg-tertiary-container/20 text-sg-tertiary border-sg-tertiary/30',
};

const emptyForm = () => ({
  name: '',
  source_type: 'webcam',
  url: '',
  username: '',
  password: '',
  location: '',
  enabled: true,
});

/**
 * Cameras management page.
 *
 * Patterns:
 *  - CRUD table patterned on ViolationsPage (header row, body rows, hover state)
 *  - Add / Edit form rendered in a Drawer (reuses Drawer.jsx)
 *  - Toggle.jsx for the `enabled` field
 *  - Test button hits /api/cameras/{id}/test and renders ok/error inline
 *
 * Validation is minimal on the client — the backend Pydantic schemas enforce
 * the real rules. We pre-check `name` to avoid a pointless round-trip.
 */
const CamerasPage = () => {
  const [cameras, setCameras] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState(null); // Camera row or null
  const [form, setForm] = useState(emptyForm());
  const [formError, setFormError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [testStatus, setTestStatus] = useState({}); // { [id]: { ok, message, loading } }

  const fetchCameras = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await listCameras();
      setCameras(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to load cameras', err);
      setCameras([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  const openAdd = () => {
    setEditing(null);
    setForm(emptyForm());
    setFormError('');
    setDrawerOpen(true);
  };

  const openEdit = (camera) => {
    setEditing(camera);
    setForm({
      name: camera.name || '',
      source_type: camera.source_type || 'webcam',
      url: camera.url || '',
      username: camera.username || '',
      password: camera.password || '',
      location: camera.location || '',
      enabled: camera.enabled !== false,
    });
    setFormError('');
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditing(null);
    setFormError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    if (!form.name.trim()) {
      setFormError('Name is required');
      return;
    }
    setIsSubmitting(true);
    try {
      // Drop empty optional fields so the server applies its own defaults
      // (e.g. webcam rows default url to "0" when omitted).
      const payload = { ...form, name: form.name.trim() };
      if (form.source_type === 'webcam') {
        // Webcam rows don't need credentials; backend rejects empty URL for
        // ip/rtsp but accepts omitted URL for webcam.
        payload.url = payload.url || '0';
        payload.username = '';
        payload.password = '';
      } else {
        if (!payload.url) {
          setFormError(`URL is required for ${form.source_type} cameras`);
          setIsSubmitting(false);
          return;
        }
      }
      if (!payload.location) delete payload.location;
      if (!payload.username) delete payload.username;
      if (!payload.password) delete payload.password;

      if (editing) {
        await updateCamera(editing.id, payload);
      } else {
        await createCamera(payload);
      }
      await fetchCameras();
      closeDrawer();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      // detail may be a string ("url is required") or a Pydantic list of errors.
      const message = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map(d => d.msg || JSON.stringify(d)).join('; ')
          : err.message || 'Request failed';
      setFormError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (camera) => {
    if (!window.confirm(`Delete camera "${camera.name}"?`)) return;
    try {
      await deleteCamera(camera.id);
      await fetchCameras();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      window.alert(typeof detail === 'string' ? detail : 'Failed to delete camera');
    }
  };

  const handleTest = async (camera) => {
    setTestStatus(prev => ({ ...prev, [camera.id]: { loading: true } }));
    try {
      const res = await testCamera(camera.id);
      setTestStatus(prev => ({ ...prev, [camera.id]: { loading: false, ok: res.data.ok, message: res.data.message } }));
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setTestStatus(prev => ({
        ...prev,
        [camera.id]: {
          loading: false,
          ok: false,
          message: typeof detail === 'string' ? detail : 'Test failed',
        },
      }));
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Page Header */}
      <div className="flex justify-between items-end mb-8">
        <div>
          <h3 className="font-headline-lg text-sg-on-surface mb-1">{cameras.length} Cameras</h3>
          <p className="font-body-md text-sg-on-surface-variant">Manage IP, RTSP and webcam feeds</p>
        </div>
        <button
          onClick={openAdd}
          className="flex items-center gap-2 px-4 py-2 bg-sg-primary text-sg-on-primary font-medium rounded hover:bg-sg-primary-fixed transition-all duration-200 shadow-[0_0_15px_rgba(255,182,147,0.15)] hover:shadow-[0_0_20px_rgba(255,182,147,0.25)]"
        >
          <span className="material-symbols-outlined text-sm">add</span>
          <span className="font-body-md font-bold">Add Camera</span>
        </button>
      </div>

      {/* Table */}
      <div className="bg-sg-surface-container border border-sg-outline-variant rounded-xl overflow-hidden flex flex-col shadow-lg shadow-black/20 flex-1">
        <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-sg-outline-variant bg-sg-surface-container-low">
          <div className="col-span-3 font-label-caps text-sg-on-surface-variant">Name</div>
          <div className="col-span-2 font-label-caps text-sg-on-surface-variant">Source</div>
          <div className="col-span-3 font-label-caps text-sg-on-surface-variant">URL / Index</div>
          <div className="col-span-2 font-label-caps text-sg-on-surface-variant">Location</div>
          <div className="col-span-1 font-label-caps text-sg-on-surface-variant">Status</div>
          <div className="col-span-1 font-label-caps text-sg-on-surface-variant text-right">Actions</div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-16 gap-3">
              <div className="w-5 h-5 border-2 border-sg-primary/30 border-t-sg-primary rounded-full animate-spin"></div>
              <span className="font-body-md text-sg-on-surface-variant">Loading cameras...</span>
            </div>
          ) : cameras.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16">
              <span className="material-symbols-outlined text-4xl text-sg-surface-bright mb-3">videocam</span>
              <p className="font-body-md text-sg-on-surface-variant mb-4">No cameras registered yet.</p>
              <button
                onClick={openAdd}
                className="flex items-center gap-2 px-4 py-2 bg-sg-primary text-sg-on-primary font-medium rounded hover:bg-sg-primary-fixed transition-all"
              >
                <span className="material-symbols-outlined text-sm">add</span>
                <span className="font-body-md font-bold">Add your first camera</span>
              </button>
            </div>
          ) : (
            cameras.map((c, idx) => {
              const status = testStatus[c.id];
              return (
                <div
                  key={c.id}
                  className="grid grid-cols-12 gap-4 px-6 py-3 items-center border-b border-sg-outline-variant/50 hover:bg-sg-surface-variant transition-colors duration-150 animate-stagger-1"
                  style={{ animationDelay: `${(idx + 1) * 50}ms` }}
                >
                  <div className="col-span-3 font-body-md text-sg-on-surface truncate">
                    <div className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-sg-on-surface-variant text-base">videocam</span>
                      <span className="font-medium">{c.name}</span>
                    </div>
                    {status && !status.loading && (
                      <p className={`font-label-caps text-[10px] mt-1 ${status.ok ? 'text-sg-tertiary' : 'text-sg-error'}`}>
                        {status.ok ? 'OK' : 'FAIL'} &mdash; {status.message}
                      </p>
                    )}
                  </div>
                  <div className="col-span-2">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border uppercase ${SOURCE_TYPE_STYLES[c.source_type] || 'bg-sg-surface-container-high text-sg-on-surface-variant border-sg-outline-variant'}`}>
                      {c.source_type}
                    </span>
                  </div>
                  <div className="col-span-3 font-data-mono text-sg-on-surface-variant text-sm truncate">
                    {c.source_type === 'webcam' ? `index ${c.url || '0'}` : c.url || '—'}
                  </div>
                  <div className="col-span-2 font-body-md text-sg-on-surface-variant truncate">
                    {c.location || '—'}
                  </div>
                  <div className="col-span-1">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${c.enabled ? 'bg-sg-tertiary-container/20 text-sg-tertiary border-sg-tertiary/30' : 'bg-sg-surface-container-high text-sg-on-surface-variant border-sg-outline-variant'}`}>
                      <span className="material-symbols-outlined text-[12px]">{c.enabled ? 'check_circle' : 'cancel'}</span>
                      {c.enabled ? 'On' : 'Off'}
                    </span>
                  </div>
                  <div className="col-span-1 flex items-center justify-end gap-1">
                    <button
                      onClick={() => handleTest(c)}
                      disabled={status?.loading}
                      title="Test connection"
                      className="p-1.5 text-sg-on-surface-variant hover:text-sg-primary hover:bg-sg-surface-container-high rounded transition-colors disabled:opacity-50"
                    >
                      <span className="material-symbols-outlined text-base">
                        {status?.loading ? 'progress_activity' : 'network_check'}
                      </span>
                    </button>
                    <button
                      onClick={() => openEdit(c)}
                      title="Edit"
                      className="p-1.5 text-sg-on-surface-variant hover:text-sg-on-surface hover:bg-sg-surface-container-high rounded transition-colors"
                    >
                      <span className="material-symbols-outlined text-base">edit</span>
                    </button>
                    <button
                      onClick={() => handleDelete(c)}
                      title="Delete"
                      className="p-1.5 text-sg-on-surface-variant hover:text-sg-error hover:bg-sg-surface-container-high rounded transition-colors"
                    >
                      <span className="material-symbols-outlined text-base">delete</span>
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Add / Edit drawer */}
      <Drawer
        open={drawerOpen}
        onClose={closeDrawer}
        title={editing ? `Edit Camera: ${editing.name}` : 'Add Camera'}
        width="520px"
      >
        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-5">
          <div className="flex flex-col gap-1">
            <label className="font-label-caps text-sg-on-surface-variant">Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Lobby Webcam"
              className="bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-body-md rounded-lg px-4 py-2 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors"
              required
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="font-label-caps text-sg-on-surface-variant">Source Type</label>
            <select
              value={form.source_type}
              onChange={(e) => setForm({ ...form, source_type: e.target.value })}
              className="bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-body-md rounded-lg px-4 py-2 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors cursor-pointer"
            >
              <option value="webcam">Webcam (local index)</option>
              <option value="ip">IP Camera (HTTP/HTTPS)</option>
              <option value="rtsp">RTSP Stream</option>
            </select>
          </div>

          {form.source_type !== 'webcam' && (
            <>
              <div className="flex flex-col gap-1">
                <label className="font-label-caps text-sg-on-surface-variant">URL</label>
                <input
                  type="text"
                  value={form.url}
                  onChange={(e) => setForm({ ...form, url: e.target.value })}
                  placeholder={form.source_type === 'rtsp' ? 'rtsp://host:554/stream' : 'http://host:8080/video'}
                  className="bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-data-mono text-sm rounded-lg px-4 py-2 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <label className="font-label-caps text-sg-on-surface-variant">Username</label>
                  <input
                    type="text"
                    value={form.username}
                    onChange={(e) => setForm({ ...form, username: e.target.value })}
                    className="bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-body-md rounded-lg px-4 py-2 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="font-label-caps text-sg-on-surface-variant">Password</label>
                  <input
                    type="password"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    className="bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-body-md rounded-lg px-4 py-2 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors"
                  />
                </div>
              </div>
            </>
          )}

          {form.source_type === 'webcam' && (
            <div className="flex flex-col gap-1">
              <label className="font-label-caps text-sg-on-surface-variant">Webcam Index</label>
              <input
                type="text"
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                placeholder="0"
                className="bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-data-mono text-sm rounded-lg px-4 py-2 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors"
              />
              <p className="font-label-caps text-[10px] text-sg-on-surface-variant">
                Defaults to 0. Use 1, 2, etc. for additional local cameras.
              </p>
            </div>
          )}

          <div className="flex flex-col gap-1">
            <label className="font-label-caps text-sg-on-surface-variant">Location (optional)</label>
            <input
              type="text"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              placeholder="e.g. Warehouse Aisle 3"
              className="bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-body-md rounded-lg px-4 py-2 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors"
            />
          </div>

          <div className="pt-2">
            <Toggle
              label="Enabled"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
          </div>

          {formError && (
            <div className="flex items-center gap-2 px-4 py-3 bg-sg-error-container/20 border border-sg-error/30 rounded text-sg-error font-body-md text-sm">
              <span className="material-symbols-outlined text-base">error</span>
              {formError}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={closeDrawer}
              className="flex-1 px-4 py-2 bg-transparent border border-sg-outline-variant text-sg-on-surface rounded hover:bg-sg-surface-container-high transition-all duration-200"
            >
              <span className="font-body-md font-medium">Cancel</span>
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 px-4 py-2 bg-sg-primary text-sg-on-primary font-medium rounded hover:bg-sg-primary-fixed transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="font-body-md font-bold">
                {isSubmitting ? 'Saving…' : editing ? 'Save Changes' : 'Add Camera'}
              </span>
            </button>
          </div>
        </form>
      </Drawer>
    </div>
  );
};

export default CamerasPage;
