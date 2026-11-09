import { useEffect, useState } from 'react';
import { Filter, RotateCw, ShieldAlert } from 'lucide-react';
import { listAdminAuditLogs } from '../services/adminApi';
import type { AdminAuditEntry } from '../types/admin';

export default function AdminAuditLogs() {
  const [logs, setLogs] = useState<AdminAuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterAction, setFilterAction] = useState('');
  const [filterResourceType, setFilterResourceType] = useState('');

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await listAdminAuditLogs({
        action: filterAction || undefined,
        resource_type: filterResourceType || undefined,
      });
      setLogs(data);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to fetch audit log entries');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [filterAction, filterResourceType]);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <ShieldAlert className="w-6 h-6 text-blue-600" />
            Administrative &amp; Subsystem Audit Trail
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Immutable system logs capturing security actions, user operations, camera updates, and model lifecycle changes.
          </p>
        </div>
        <button
          onClick={fetchLogs}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition"
        >
          <RotateCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm flex flex-wrap gap-4 items-center">
        <span className="text-xs font-semibold text-gray-600 flex items-center gap-1.5">
          <Filter className="w-4 h-4 text-blue-600" /> Filter Logs:
        </span>
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">Action:</label>
          <select
            value={filterAction}
            onChange={(e) => setFilterAction(e.target.value)}
            className="border border-gray-300 rounded px-2.5 py-1 text-xs bg-white"
          >
            <option value="">All Actions</option>
            <option value="USER_CREATED">USER_CREATED</option>
            <option value="USER_UPDATED">USER_UPDATED</option>
            <option value="USER_STATUS_CHANGED">USER_STATUS_CHANGED</option>
            <option value="PASSWORD_RESET">PASSWORD_RESET</option>
            <option value="CAMERA_REGISTERED">CAMERA_REGISTERED</option>
            <option value="CAMERA_UPDATED">CAMERA_UPDATED</option>
            <option value="CAMERA_DELETED">CAMERA_DELETED</option>
            <option value="DEPARTMENT_CREATED">DEPARTMENT_CREATED</option>
            <option value="BACKUP_CREATED">BACKUP_CREATED</option>
            <option value="BACKUP_RESTORED">BACKUP_RESTORED</option>
            <option value="MODEL_ACTIVATED">MODEL_ACTIVATED</option>
            <option value="MODEL_RETIRED">MODEL_RETIRED</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">Resource:</label>
          <select
            value={filterResourceType}
            onChange={(e) => setFilterResourceType(e.target.value)}
            className="border border-gray-300 rounded px-2.5 py-1 text-xs bg-white"
          >
            <option value="">All Resources</option>
            <option value="USER">USER</option>
            <option value="CAMERA">CAMERA</option>
            <option value="DEPARTMENT">DEPARTMENT</option>
            <option value="BACKUP">BACKUP</option>
            <option value="MODEL">MODEL</option>
            <option value="CONFIG">CONFIG</option>
          </select>
        </div>

        {(filterAction || filterResourceType) && (
          <button
            onClick={() => {
              setFilterAction('');
              setFilterResourceType('');
            }}
            className="text-xs text-blue-600 hover:underline ml-auto"
          >
            Reset Filters
          </button>
        )}
      </div>

      {/* Logs Table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-gray-600 text-xs uppercase font-semibold">
            <tr>
              <th className="px-6 py-3 text-left">Timestamp</th>
              <th className="px-6 py-3 text-left">Action</th>
              <th className="px-6 py-3 text-left">Resource</th>
              <th className="px-6 py-3 text-left">Actor ID</th>
              <th className="px-6 py-3 text-left">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-10 text-center">
                  <RotateCw className="w-6 h-6 animate-spin mx-auto text-blue-600" />
                </td>
              </tr>
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-10 text-center text-gray-500">
                  No audit log entries matching filters.
                </td>
              </tr>
            ) : (
              logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-6 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {new Date(log.timestamp).toLocaleString()}
                  </td>
                  <td className="px-6 py-3">
                    <span className="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-gray-100 text-gray-800">
                      {log.action}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-xs text-gray-600">
                    {log.resource_type} {log.resource_id ? `#${log.resource_id}` : ''}
                  </td>
                  <td className="px-6 py-3 text-xs text-gray-600 font-mono">
                    User {log.user_id}
                  </td>
                  <td className="px-6 py-3 text-xs text-gray-700">
                    {log.details || 'No additional details provided'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
