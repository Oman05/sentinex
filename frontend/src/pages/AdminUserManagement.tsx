import React, { useEffect, useState } from 'react';
import { Users, UserPlus, KeyRound, CheckCircle, XCircle, RotateCw, Edit2 } from 'lucide-react';
import {
  listAdminUsers,
  createAdminUser,
  updateAdminUser,
  updateAdminUserStatus,
  resetUserPassword,
  listAdminDepartments,
} from '../services/adminApi';
import type { AdminUser, AdminDepartment } from '../types/admin';

export default function AdminUserManagement() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [departments, setDepartments] = useState<AdminDepartment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);

  // Form states
  const [createForm, setCreateForm] = useState({
    username: '',
    email: '',
    password: '',
    role: 'POLICE',
    department_id: '',
  });

  const [editForm, setEditForm] = useState({
    email: '',
    role: '',
    department_id: '',
    is_active: true,
  });

  const [resetPasswordForm, setResetPasswordForm] = useState({
    newPassword: '',
    reason: 'Administrative security reset',
  });

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [userData, deptData] = await Promise.all([
        listAdminUsers(),
        listAdminDepartments(),
      ]);
      setUsers(userData);
      setDepartments(deptData);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load user directory');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createAdminUser({
        username: createForm.username,
        email: createForm.email,
        password: createForm.password,
        role: createForm.role,
        department_id: createForm.department_id ? parseInt(createForm.department_id) : null,
      });
      setShowCreateModal(false);
      setCreateForm({ username: '', email: '', password: '', role: 'POLICE', department_id: '' });
      fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to create user');
    }
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    try {
      await updateAdminUser(selectedUser.id, {
        email: editForm.email,
        role: editForm.role,
        department_id: editForm.department_id ? parseInt(editForm.department_id) : null,
        is_active: editForm.is_active,
      });
      setShowEditModal(false);
      fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to update user');
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    try {
      await resetUserPassword(selectedUser.id, resetPasswordForm.newPassword, resetPasswordForm.reason);
      setShowResetModal(false);
      setResetPasswordForm({ newPassword: '', reason: 'Administrative security reset' });
      alert('Password updated successfully');
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to reset password');
    }
  };

  const handleToggleStatus = async (user: AdminUser) => {
    try {
      await updateAdminUserStatus(user.id, !user.is_active);
      fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to update status');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Users className="w-6 h-6 text-blue-600" />
            User Management &amp; Role-Based Access Control
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage administrative officers, field investigators, reviewers, and research permissions.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 transition"
        >
          <UserPlus className="w-4 h-4" />
          Add Authorized User
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md text-sm">{error}</div>
      )}

      {/* User Table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-gray-600 text-xs uppercase tracking-wider font-semibold">
              <tr>
                <th className="px-6 py-3 text-left">Username</th>
                <th className="px-6 py-3 text-left">Email Address</th>
                <th className="px-6 py-3 text-left">Role</th>
                <th className="px-6 py-3 text-left">Department</th>
                <th className="px-6 py-3 text-left">Status</th>
                <th className="px-6 py-3 text-left">Last Login</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-10 text-center text-gray-500">
                    <RotateCw className="w-6 h-6 animate-spin mx-auto text-blue-600" />
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-10 text-center text-gray-500">
                    No users registered.
                  </td>
                </tr>
              ) : (
                users.map((u) => {
                  const dept = departments.find((d) => d.id === u.department_id);
                  return (
                    <tr key={u.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 font-medium text-gray-900">{u.username}</td>
                      <td className="px-6 py-4 text-gray-600">{u.email}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                          u.role === 'ADMIN' ? 'bg-purple-100 text-purple-800' :
                          u.role === 'AUTHORIZED_OFFICER' || u.role === 'POLICE' ? 'bg-blue-100 text-blue-800' :
                          u.role === 'REVIEWER' ? 'bg-emerald-100 text-emerald-800' :
                          'bg-amber-100 text-amber-800'
                        }`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-gray-600">
                        {dept ? dept.department_name : <span className="text-gray-400">All / Central</span>}
                      </td>
                      <td className="px-6 py-4">
                        <button
                          onClick={() => handleToggleStatus(u)}
                          className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-medium cursor-pointer ${
                            u.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {u.is_active ? (
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
                        {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'Never'}
                      </td>
                      <td className="px-6 py-4 text-right space-x-2">
                        <button
                          onClick={() => {
                            setSelectedUser(u);
                            setEditForm({
                              email: u.email,
                              role: u.role,
                              department_id: u.department_id ? String(u.department_id) : '',
                              is_active: u.is_active,
                            });
                            setShowEditModal(true);
                          }}
                          className="text-gray-500 hover:text-blue-600 p-1"
                          title="Edit User"
                        >
                          <Edit2 className="w-4 h-4 inline" />
                        </button>
                        <button
                          onClick={() => {
                            setSelectedUser(u);
                            setShowResetModal(true);
                          }}
                          className="text-gray-500 hover:text-amber-600 p-1"
                          title="Reset Password"
                        >
                          <KeyRound className="w-4 h-4 inline" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-gray-900">Add Authorized User</h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700">Username</label>
                <input
                  type="text"
                  required
                  value={createForm.username}
                  onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700">Email Address</label>
                <input
                  type="email"
                  required
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700">Temporary Password</label>
                <input
                  type="password"
                  required
                  value={createForm.password}
                  onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700">Role</label>
                <select
                  value={createForm.role}
                  onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm bg-white"
                >
                  <option value="ADMIN">ADMIN (Full System Control)</option>
                  <option value="AUTHORIZED_OFFICER">AUTHORIZED_OFFICER (Case &amp; CCTV Operator)</option>
                  <option value="POLICE">POLICE (Standard Officer)</option>
                  <option value="REVIEWER">REVIEWER (Human Verification &amp; Investigation)</option>
                  <option value="RESEARCHER">RESEARCHER (Evaluation &amp; Model Benchmark)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700">Assigned Department</label>
                <select
                  value={createForm.department_id}
                  onChange={(e) => setCreateForm({ ...createForm, department_id: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm bg-white"
                >
                  <option value="">None / Central Headquarters</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.department_name} ({d.department_type})
                    </option>
                  ))}
                </select>
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
                  Create User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {showEditModal && selectedUser && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-gray-900">Edit User: {selectedUser.username}</h2>
            <form onSubmit={handleEdit} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700">Email Address</label>
                <input
                  type="email"
                  required
                  value={editForm.email}
                  onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700">Role</label>
                <select
                  value={editForm.role}
                  onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm bg-white"
                >
                  <option value="ADMIN">ADMIN</option>
                  <option value="AUTHORIZED_OFFICER">AUTHORIZED_OFFICER</option>
                  <option value="POLICE">POLICE</option>
                  <option value="REVIEWER">REVIEWER</option>
                  <option value="RESEARCHER">RESEARCHER</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700">Assigned Department</label>
                <select
                  value={editForm.department_id}
                  onChange={(e) => setEditForm({ ...editForm, department_id: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm bg-white"
                >
                  <option value="">None / Central Headquarters</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.department_name} ({d.department_type})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="userActive"
                  checked={editForm.is_active}
                  onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                  className="rounded text-blue-600"
                />
                <label htmlFor="userActive" className="text-sm text-gray-700">User is active and authorized to log in</label>
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

      {/* Password Reset Modal */}
      {showResetModal && selectedUser && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-gray-900">Administrative Password Reset</h2>
            <p className="text-sm text-gray-600">
              Reset login credentials for user: <span className="font-semibold">{selectedUser.username}</span>
            </p>
            <form onSubmit={handleResetPassword} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700">New Password (min 8 characters)</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={resetPasswordForm.newPassword}
                  onChange={(e) => setResetPasswordForm({ ...resetPasswordForm, newPassword: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700">Audit Justification / Reason</label>
                <input
                  type="text"
                  required
                  value={resetPasswordForm.reason}
                  onChange={(e) => setResetPasswordForm({ ...resetPasswordForm, reason: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-4 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowResetModal(false)}
                  className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm bg-amber-600 text-white font-medium rounded hover:bg-amber-700"
                >
                  Reset Password
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
