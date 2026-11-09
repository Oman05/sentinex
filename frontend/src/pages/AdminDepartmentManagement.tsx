import React, { useEffect, useState } from 'react';
import { Building2, Plus, BarChart2, CheckCircle, XCircle, RotateCw, Edit } from 'lucide-react';
import {
  listAdminDepartments,
  createAdminDepartment,
  updateAdminDepartment,
  updateAdminDepartmentStatus,
  getDepartmentStats,
} from '../services/adminApi';
import type { AdminDepartment, DepartmentStats } from '../types/admin';

export default function AdminDepartmentManagement() {
  const [departments, setDepartments] = useState<AdminDepartment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showStatsModal, setShowStatsModal] = useState(false);
  const [selectedDept, setSelectedDept] = useState<AdminDepartment | null>(null);
  const [statsData, setStatsData] = useState<DepartmentStats | null>(null);

  const [createForm, setCreateForm] = useState({
    department_name: '',
    department_type: 'POLICE',
    location: '',
  });

  const [editForm, setEditForm] = useState({
    department_name: '',
    department_type: '',
    location: '',
  });

  const fetchDepartments = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAdminDepartments();
      setDepartments(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load departments');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDepartments();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createAdminDepartment(createForm);
      setShowCreateModal(false);
      setCreateForm({ department_name: '', department_type: 'POLICE', location: '' });
      fetchDepartments();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to create department');
    }
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDept) return;
    try {
      await updateAdminDepartment(selectedDept.id, editForm);
      setShowEditModal(false);
      fetchDepartments();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to update department');
    }
  };

  const handleToggleStatus = async (dept: AdminDepartment) => {
    try {
      await updateAdminDepartmentStatus(dept.id, !dept.is_active);
      fetchDepartments();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to update status');
    }
  };

  const handleViewStats = async (dept: AdminDepartment) => {
    setSelectedDept(dept);
    try {
      const stats = await getDepartmentStats(dept.id);
      setStatsData(stats);
      setShowStatsModal(true);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to load department statistics');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Building2 className="w-6 h-6 text-blue-600" />
            Department &amp; Jurisdiction Management
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Configure agency jurisdictions, contact nodes, camera allocations, and alert dispatch hierarchies.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 transition"
        >
          <Plus className="w-4 h-4" />
          Add Department
        </button>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded text-sm">{error}</div>}

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-gray-600 text-xs uppercase tracking-wider font-semibold">
            <tr>
              <th className="px-6 py-3 text-left">Department Name</th>
              <th className="px-6 py-3 text-left">Agency Type</th>
              <th className="px-6 py-3 text-left">Jurisdiction / Location</th>
              <th className="px-6 py-3 text-left">Status</th>
              <th className="px-6 py-3 text-left">Created Date</th>
              <th className="px-6 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-6 py-10 text-center">
                  <RotateCw className="w-6 h-6 animate-spin mx-auto text-blue-600" />
                </td>
              </tr>
            ) : departments.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-10 text-center text-gray-500">
                  No departments configured.
                </td>
              </tr>
            ) : (
              departments.map((d) => (
                <tr key={d.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-medium text-gray-900">{d.department_name}</td>
                  <td className="px-6 py-4 text-gray-600">
                    <span className="px-2.5 py-0.5 rounded text-xs bg-gray-100 font-semibold text-gray-800">
                      {d.department_type}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-600">{d.location || 'All Jurisdictions'}</td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => handleToggleStatus(d)}
                      className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-medium ${
                        d.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}
                    >
                      {d.is_active ? (
                        <>
                          <CheckCircle className="w-3.5 h-3.5 text-green-600" /> Active
                        </>
                      ) : (
                        <>
                          <XCircle className="w-3.5 h-3.5 text-red-600" /> Inactive
                        </>
                      )}
                    </button>
                  </td>
                  <td className="px-6 py-4 text-gray-500 text-xs">
                    {new Date(d.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <button
                      onClick={() => handleViewStats(d)}
                      className="text-gray-500 hover:text-blue-600 p-1"
                      title="View Department Telemetry"
                    >
                      <BarChart2 className="w-4 h-4 inline" />
                    </button>
                    <button
                      onClick={() => {
                        setSelectedDept(d);
                        setEditForm({
                          department_name: d.department_name,
                          department_type: d.department_type,
                          location: d.location || '',
                        });
                        setShowEditModal(true);
                      }}
                      className="text-gray-500 hover:text-gray-800 p-1"
                      title="Edit Department"
                    >
                      <Edit className="w-4 h-4 inline" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create Department Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-gray-900">Add Department</h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700">Department Name</label>
                <input
                  type="text"
                  required
                  value={createForm.department_name}
                  onChange={(e) => setCreateForm({ ...createForm, department_name: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                  placeholder="e.g. Central City Police Command"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700">Department Type</label>
                <select
                  value={createForm.department_type}
                  onChange={(e) => setCreateForm({ ...createForm, department_type: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm bg-white"
                >
                  <option value="POLICE">POLICE</option>
                  <option value="TRANSIT_SECURITY">TRANSIT_SECURITY</option>
                  <option value="AIRPORT_SECURITY">AIRPORT_SECURITY</option>
                  <option value="PORT_AUTHORITY">PORT_AUTHORITY</option>
                  <option value="CAMPUS_SECURITY">CAMPUS_SECURITY</option>
                  <option value="INVESTIGATION_UNIT">INVESTIGATION_UNIT</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700">Jurisdiction / Location</label>
                <input
                  type="text"
                  value={createForm.location}
                  onChange={(e) => setCreateForm({ ...createForm, location: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                  placeholder="e.g. Sector 4, North Zone"
                />
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
                  Create Department
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Department Modal */}
      {showEditModal && selectedDept && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-gray-900">Edit Department</h2>
            <form onSubmit={handleEdit} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700">Department Name</label>
                <input
                  type="text"
                  required
                  value={editForm.department_name}
                  onChange={(e) => setEditForm({ ...editForm, department_name: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700">Agency Type</label>
                <input
                  type="text"
                  required
                  value={editForm.department_type}
                  onChange={(e) => setEditForm({ ...editForm, department_type: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700">Jurisdiction / Location</label>
                <input
                  type="text"
                  value={editForm.location}
                  onChange={(e) => setEditForm({ ...editForm, location: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-4 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm bg-blue-600 text-white font-medium rounded hover:bg-blue-700"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Department Stats Modal */}
      {showStatsModal && statsData && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-gray-900">{statsData.department_name} Telemetry</h2>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="p-3 bg-gray-50 rounded border border-gray-200">
                <span className="text-xs text-gray-500 block">Total Users</span>
                <span className="text-lg font-bold text-gray-900">{statsData.total_users}</span>
              </div>
              <div className="p-3 bg-gray-50 rounded border border-gray-200">
                <span className="text-xs text-gray-500 block">Active Cases</span>
                <span className="text-lg font-bold text-gray-900">{statsData.total_cases}</span>
              </div>
              <div className="p-3 bg-gray-50 rounded border border-gray-200">
                <span className="text-xs text-gray-500 block">Assigned Cameras</span>
                <span className="text-lg font-bold text-gray-900">
                  {statsData.online_cameras} / {statsData.total_cameras} Online
                </span>
              </div>
              <div className="p-3 bg-gray-50 rounded border border-gray-200">
                <span className="text-xs text-gray-500 block">Alert Dispatches</span>
                <span className="text-lg font-bold text-blue-600">{statsData.total_alerts_dispatched} Sent</span>
              </div>
            </div>
            <div className="flex justify-end pt-4 border-t border-gray-200">
              <button
                type="button"
                onClick={() => setShowStatsModal(false)}
                className="px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
