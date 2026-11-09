import { useState, useEffect } from 'react';
import {
  ShieldAlert,
  Search,
  RefreshCw,
  Lock,
  User,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import type { AuditLogItem } from '../types/evidence';
import { listAuditLogs } from '../services/evidenceApi';

export default function AuditDashboard() {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  // Filters (Section 34: User, Department, Action, Resource, Date, Result)
  const [userFilter, setUserFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [resourceTypeFilter, setResourceTypeFilter] = useState('');
  const [resourceIdFilter, setResourceIdFilter] = useState('');
  const [resultFilter, setResultFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const res = await listAuditLogs({
        user: userFilter || undefined,
        action: actionFilter || undefined,
        resource_type: resourceTypeFilter || undefined,
        resource_id: resourceIdFilter || undefined,
        result: resultFilter || undefined,
        date_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
        date_to: dateTo ? new Date(dateTo).toISOString() : undefined,
        page,
        page_size: 25,
      });
      setLogs(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error('Failed to load audit logs', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [userFilter, actionFilter, resourceTypeFilter, resourceIdFilter, resultFilter, page]);

  const handleResetFilters = () => {
    setUserFilter('');
    setActionFilter('');
    setResourceTypeFilter('');
    setResourceIdFilter('');
    setResultFilter('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-2.5">
            <ShieldAlert className="w-7 h-7 text-amber-600" />
            SYSTEM AUDIT TRAIL
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Section 16–18 • Append-only immutable log of every sensitive action (Who, What, When, Where, Why)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-3 py-1 bg-amber-100 text-amber-900 font-bold text-xs rounded-full border border-amber-300 flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5" />
            AUDITOR / ADMIN PRIVILEGE
          </span>
        </div>
      </div>

      {/* Filter Toolbar (Section 34) */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
          <div>
            <label className="block text-gray-600 font-medium mb-1">User / Actor</label>
            <input
              type="text"
              placeholder="e.g. Officer-102"
              value={userFilter}
              onChange={(e) => setUserFilter(e.target.value)}
              className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-gray-600 font-medium mb-1">Action</label>
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="">All Actions</option>
              <option value="EVIDENCE_VIEW">EVIDENCE_VIEW</option>
              <option value="EVIDENCE_CREATE">EVIDENCE_CREATE</option>
              <option value="EVIDENCE_DOWNLOAD">EVIDENCE_DOWNLOAD</option>
              <option value="EVIDENCE_UPDATE">EVIDENCE_UPDATE</option>
              <option value="EVIDENCE_ARCHIVE">EVIDENCE_ARCHIVE</option>
              <option value="EVIDENCE_FINALIZE">EVIDENCE_FINALIZE</option>
              <option value="EVIDENCE_INTEGRITY_CHECK">EVIDENCE_INTEGRITY_CHECK</option>
              <option value="UNAUTHORIZED_ACCESS_ATTEMPT">UNAUTHORIZED_ACCESS_ATTEMPT</option>
              <option value="LOGIN">LOGIN</option>
              <option value="CASE_VIEW">CASE_VIEW</option>
              <option value="ALERT_CREATE">ALERT_CREATE</option>
              <option value="ALERT_ACKNOWLEDGE">ALERT_ACKNOWLEDGE</option>
            </select>
          </div>

          <div>
            <label className="block text-gray-600 font-medium mb-1">Resource Type</label>
            <select
              value={resourceTypeFilter}
              onChange={(e) => setResourceTypeFilter(e.target.value)}
              className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="">All Resources</option>
              <option value="EVIDENCE">EVIDENCE</option>
              <option value="CASE">CASE</option>
              <option value="ALERT">ALERT</option>
              <option value="USER">USER</option>
              <option value="RETENTION_POLICY">RETENTION_POLICY</option>
            </select>
          </div>

          <div>
            <label className="block text-gray-600 font-medium mb-1">Resource ID</label>
            <input
              type="text"
              placeholder="e.g. EVD-2026-000001"
              value={resourceIdFilter}
              onChange={(e) => setResourceIdFilter(e.target.value)}
              className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-gray-600 font-medium mb-1">Result</label>
            <select
              value={resultFilter}
              onChange={(e) => setResultFilter(e.target.value)}
              className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="">All Results</option>
              <option value="SUCCESS">SUCCESS</option>
              <option value="FAILURE">FAILURE</option>
              <option value="DENIED">DENIED</option>
            </select>
          </div>

          <div className="flex items-end gap-2">
            <button
              onClick={fetchLogs}
              className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold flex items-center justify-center gap-1"
            >
              <Search className="w-3.5 h-3.5" /> Filter
            </button>
            <button
              onClick={handleResetFilters}
              className="p-2 border border-gray-300 hover:bg-gray-100 rounded-lg text-gray-600"
              title="Reset Filters"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Audit Log Table (Section 34 Layout) */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-gray-500 uppercase tracking-wider font-semibold">
                <th className="py-3 px-4">Event ID</th>
                <th className="py-3 px-4">User</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Resource</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Result</th>
                <th className="py-3 px-4">Reason / Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 font-medium text-gray-700">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-gray-400">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                    Loading system audit records...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-gray-400">
                    No audit records match the selected criteria.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50/60 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-blue-600">
                      {log.event_id}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1.5 font-semibold text-gray-900">
                        <User className="w-3.5 h-3.5 text-gray-400" />
                        {log.actor_username || 'SYSTEM'}
                      </div>
                      {log.ip_address && (
                        <div className="text-[10px] text-gray-400 font-mono mt-0.5">{log.ip_address}</div>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-semibold text-gray-800">{log.action}</span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-mono text-gray-900 font-semibold">{log.resource_type}</div>
                      <div className="text-[11px] text-gray-500 font-mono">{log.resource_label || log.resource_id || '—'}</div>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap text-gray-600 font-mono">
                      <div>{new Date(log.timestamp).toLocaleTimeString([], { hour12: false })}</div>
                      <div className="text-[10px] text-gray-400">{new Date(log.timestamp).toLocaleDateString()}</div>
                    </td>
                    <td className="py-3 px-4">
                      {log.result === 'SUCCESS' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-green-100 text-green-800">
                          <CheckCircle2 className="w-3 h-3 text-green-600" /> OK
                        </span>
                      )}
                      {log.result === 'DENIED' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-rose-100 text-rose-800">
                          <XCircle className="w-3 h-3 text-rose-600" /> DENIED
                        </span>
                      )}
                      {log.result === 'FAILURE' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-800">
                          <AlertTriangle className="w-3 h-3 text-amber-600" /> FAIL
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 max-w-xs truncate text-gray-500 italic">
                      {log.reason || '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 25 && (
          <div className="flex items-center justify-between p-4 bg-gray-50 border-t border-gray-200 text-xs text-gray-600">
            <span>
              Showing {(page - 1) * 25 + 1} to {Math.min(page * 25, total)} of {total} audit records
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 bg-white border border-gray-300 rounded disabled:opacity-40"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page * 25 >= total}
                className="px-3 py-1 bg-white border border-gray-300 rounded disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
