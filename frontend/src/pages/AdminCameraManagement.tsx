import React, { useEffect, useState } from 'react';
import { Camera, Plus, CheckCircle, XCircle, RotateCw, Wifi, Trash2 } from 'lucide-react';
import {
  listAdminCameras,
  createAdminCamera,
  deleteAdminCamera,
  testCameraConnection,
  listAdminDepartments,
} from '../services/adminApi';
import type { AdminCamera, AdminDepartment } from '../types/admin';

export default function AdminCameraManagement() {
  const [cameras, setCameras] = useState<AdminCamera[]>([]);
  const [departments, setDepartments] = useState<AdminDepartment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({
    camera_name: '',
    department_id: '',
    location_name: '',
    stream_url: '',
    stream_type: 'RTSP',
    sample_fps: 1.0,
    sampling_interval: 1.0,
    username: '',
    password: '',
  });

  const fetchCameras = async () => {
    setLoading(true);
    setError(null);
    try {
      const [cams, depts] = await Promise.all([
        listAdminCameras(),
        listAdminDepartments(),
      ]);
      setCameras(cams);
      setDepartments(depts);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load camera registry');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCameras();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createAdminCamera({
        camera_name: createForm.camera_name,
        department_id: parseInt(createForm.department_id),
        location_name: createForm.location_name,
        stream_url: createForm.stream_url,
        stream_type: createForm.stream_type,
        sample_fps: parseFloat(String(createForm.sample_fps)),
        sampling_interval: parseFloat(String(createForm.sampling_interval)),
        username: createForm.username || null,
        password: createForm.password || null,
      });
      setShowCreateModal(false);
      setCreateForm({
        camera_name: '',
        department_id: '',
        location_name: '',
        stream_url: '',
        stream_type: 'RTSP',
        sample_fps: 1.0,
        sampling_interval: 1.0,
        username: '',
        password: '',
      });
      fetchCameras();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to register camera');
    }
  };

  const handleTestConnection = async (cameraId: number) => {
    setTestingId(cameraId);
    try {
      const res = await testCameraConnection(cameraId);
      alert(`Connection Test ${res.connection_test}: ${res.stream_url_scheme} stream latency is ${res.latency_ms}ms.`);
      fetchCameras();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Connection test failed');
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async (camera: AdminCamera) => {
    if (!window.confirm(`Are you sure you want to remove authorized camera '${camera.camera_name}'?`)) {
      return;
    }
    try {
      await deleteAdminCamera(camera.id);
      fetchCameras();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to delete camera');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Camera className="w-6 h-6 text-blue-600" />
            Authorized CCTV &amp; IP Camera Management
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Register authorized cameras, configure frame sampling rates, and manage secure ingestion workers.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 transition"
        >
          <Plus className="w-4 h-4" />
          Register Authorized Camera
        </button>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded text-sm">{error}</div>}

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-gray-600 text-xs uppercase tracking-wider font-semibold">
            <tr>
              <th className="px-6 py-3 text-left">Camera Name &amp; Code</th>
              <th className="px-6 py-3 text-left">Department</th>
              <th className="px-6 py-3 text-left">Location</th>
              <th className="px-6 py-3 text-left">Type &amp; FPS</th>
              <th className="px-6 py-3 text-left">Status</th>
              <th className="px-6 py-3 text-left">Last Seen</th>
              <th className="px-6 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-6 py-10 text-center">
                  <RotateCw className="w-6 h-6 animate-spin mx-auto text-blue-600" />
                </td>
              </tr>
            ) : cameras.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-10 text-center text-gray-500">
                  No authorized cameras registered.
                </td>
              </tr>
            ) : (
              cameras.map((c) => {
                const dept = departments.find((d) => d.id === c.department_id);
                const isOnline = c.status === 'ONLINE' || c.status === 'ACTIVE';
                return (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="font-medium text-gray-900">{c.camera_name}</div>
                      <div className="text-xs text-gray-400 font-mono">{c.camera_code}</div>
                    </td>
                    <td className="px-6 py-4 text-gray-600">{dept?.department_name || `Dept #${c.department_id}`}</td>
                    <td className="px-6 py-4 text-gray-600">{c.location_name || 'N/A'}</td>
                    <td className="px-6 py-4 text-gray-600">
                      <span className="font-mono text-xs font-semibold">{c.stream_type}</span> @ {c.sample_fps} FPS
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-medium ${
                        isOnline ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                      }`}>
                        {isOnline ? (
                          <>
                            <CheckCircle className="w-3.5 h-3.5 text-green-600" /> {c.status}
                          </>
                        ) : (
                          <>
                            <XCircle className="w-3.5 h-3.5 text-gray-400" /> {c.status}
                          </>
                        )}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs text-gray-400">
                      {c.last_seen_at ? new Date(c.last_seen_at).toLocaleTimeString() : 'Never'}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <button
                        onClick={() => handleTestConnection(c.id)}
                        disabled={testingId === c.id}
                        className="text-gray-500 hover:text-blue-600 p-1"
                        title="Test Connection"
                      >
                        <Wifi className={`w-4 h-4 inline ${testingId === c.id ? 'animate-pulse text-blue-600' : ''}`} />
                      </button>
                      <button
                        onClick={() => handleDelete(c)}
                        className="text-gray-400 hover:text-red-600 p-1"
                        title="Delete Camera"
                      >
                        <Trash2 className="w-4 h-4 inline" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Add Camera Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-gray-900">Register Authorized Camera</h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700">Camera Name / Identifier</label>
                <input
                  type="text"
                  required
                  value={createForm.camera_name}
                  onChange={(e) => setCreateForm({ ...createForm, camera_name: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                  placeholder="e.g. Terminal 1 Gate Entrance North"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700">Department</label>
                  <select
                    required
                    value={createForm.department_id}
                    onChange={(e) => setCreateForm({ ...createForm, department_id: e.target.value })}
                    className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm bg-white"
                  >
                    <option value="">Select Department</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.department_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700">Stream Type</label>
                  <select
                    value={createForm.stream_type}
                    onChange={(e) => setCreateForm({ ...createForm, stream_type: e.target.value })}
                    className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm bg-white"
                  >
                    <option value="RTSP">RTSP</option>
                    <option value="HTTP">HTTP</option>
                    <option value="HTTPS">HTTPS</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700">Stream URL (Without Credentials)</label>
                <input
                  type="text"
                  required
                  value={createForm.stream_url}
                  onChange={(e) => setCreateForm({ ...createForm, stream_url: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm font-mono text-xs"
                  placeholder="rtsp://192.168.1.100:554/stream1"
                />
                <span className="text-[11px] text-gray-400">Strict Rule: Stream URL must not contain embedded user credentials.</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700">Stream Username (Optional)</label>
                  <input
                    type="text"
                    value={createForm.username}
                    onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
                    className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700">Encrypted Password (Optional)</label>
                  <input
                    type="password"
                    value={createForm.password}
                    onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                    className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700">Sample FPS</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    max="30"
                    value={createForm.sample_fps}
                    onChange={(e) => setCreateForm({ ...createForm, sample_fps: parseFloat(e.target.value) })}
                    className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700">Sampling Interval (sec)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    max="60"
                    value={createForm.sampling_interval}
                    onChange={(e) => setCreateForm({ ...createForm, sampling_interval: parseFloat(e.target.value) })}
                    className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-2 pt-4 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm bg-blue-600 text-white font-medium rounded hover:bg-blue-700"
                >
                  Register Camera
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
