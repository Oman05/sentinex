import { useEffect, useState } from "react";
import {
  Bell,
  Search,
  Filter,
  CheckCircle2,
  Clock,
  PlayCircle,
  XCircle,
  ShieldAlert,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import type { AlertDashboardStats, AlertFilters, AlertItem } from '../types/alert';
import { getAlertDashboardStats, listAlerts } from '../services/alertApi';
import { AlertCard } from '../components/AlertCard';

export default function AlertDashboard() {
  const [stats, setStats] = useState<AlertDashboardStats | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<AlertFilters>({});
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [searchInput, setSearchInput] = useState('');

  const fetchData = async () => {
    try {
      setLoading(true);
      const [statsRes, listRes] = await Promise.all([
        getAlertDashboardStats(),
        listAlerts(filters, page, 12),
      ]);
      setStats(statsRes);
      setAlerts(listRes.items);
      setTotalPages(listRes.pages);
    } catch (err) {
      console.error('Failed to load alert dashboard', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [filters, page]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setFilters((prev) => ({ ...prev, case_number: searchInput || undefined }));
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-2">
            <Bell className="w-6 h-6 text-blue-600" />
            Module 9: Alert &amp; Department Notification Center
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Authorized operational alerts routed strictly following Module 8 human verification.
          </p>
        </div>

        <button
          onClick={fetchData}
          disabled={loading}
          className="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-xs font-semibold px-3 py-2 rounded-md shadow-sm flex items-center gap-1.5 transition-colors self-start md:self-auto disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Queue
        </button>
      </div>

      {/* Aggregate Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          <div className="bg-white border border-gray-200 rounded-lg p-3.5 shadow-sm">
            <div className="text-[11px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1">
              <ShieldAlert className="w-3.5 h-3.5 text-blue-600" /> Total Alerts
            </div>
            <div className="text-2xl font-black text-gray-900 mt-1">{stats.total_alerts}</div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-3.5 shadow-sm">
            <div className="text-[11px] font-bold text-amber-600 uppercase tracking-wider flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-amber-500" /> Pending Ack
            </div>
            <div className="text-2xl font-black text-amber-700 mt-1">{stats.pending}</div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-3.5 shadow-sm">
            <div className="text-[11px] font-bold text-indigo-600 uppercase tracking-wider flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-indigo-500" /> Acknowledged
            </div>
            <div className="text-2xl font-black text-indigo-700 mt-1">{stats.acknowledged}</div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-3.5 shadow-sm">
            <div className="text-[11px] font-bold text-purple-600 uppercase tracking-wider flex items-center gap-1">
              <PlayCircle className="w-3.5 h-3.5 text-purple-500" /> In Progress
            </div>
            <div className="text-2xl font-black text-purple-700 mt-1">{stats.in_progress}</div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-3.5 shadow-sm">
            <div className="text-[11px] font-bold text-emerald-600 uppercase tracking-wider flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> Resolved
            </div>
            <div className="text-2xl font-black text-emerald-700 mt-1">{stats.resolved}</div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-3.5 shadow-sm">
            <div className="text-[11px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1">
              <XCircle className="w-3.5 h-3.5 text-gray-400" /> Closed
            </div>
            <div className="text-2xl font-black text-gray-700 mt-1">{stats.closed}</div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-3.5 shadow-sm">
            <div className="text-[11px] font-bold text-teal-600 uppercase tracking-wider flex items-center gap-1">
              <Filter className="w-3.5 h-3.5 text-teal-500" /> Dedup Filtered
            </div>
            <div className="text-2xl font-black text-teal-700 mt-1">{stats.duplicate_alerts_prevented}</div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm flex flex-col md:flex-row gap-3 items-center justify-between">
        <form onSubmit={handleSearch} className="flex-1 flex gap-2 w-full md:w-auto">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by Case Number (e.g. WP-2026-0001)..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs border border-gray-300 rounded-md focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none"
            />
          </div>
          <button
            type="submit"
            className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-1.5 rounded-md transition-colors shadow-sm"
          >
            Search
          </button>
        </form>

        <div className="flex flex-wrap gap-2 w-full md:w-auto">
          <select
            value={filters.status || ''}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, status: e.target.value || undefined }));
              setPage(1);
            }}
            className="text-xs border border-gray-300 rounded-md px-2.5 py-1.5 bg-white text-gray-700 outline-none focus:border-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="DELIVERED">Delivered</option>
            <option value="ACKNOWLEDGED">Acknowledged</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="RESOLVED">Resolved</option>
            <option value="CLOSED">Closed</option>
          </select>

          <select
            value={filters.priority || ''}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, priority: e.target.value || undefined }));
              setPage(1);
            }}
            className="text-xs border border-gray-300 rounded-md px-2.5 py-1.5 bg-white text-gray-700 outline-none focus:border-blue-500"
          >
            <option value="">All Priorities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="NORMAL">Normal</option>
            <option value="LOW">Low</option>
          </select>

          <select
            value={filters.category || ''}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, category: e.target.value || undefined }));
              setPage(1);
            }}
            className="text-xs border border-gray-300 rounded-md px-2.5 py-1.5 bg-white text-gray-700 outline-none focus:border-blue-500"
          >
            <option value="">All Categories</option>
            <option value="WANTED">Wanted</option>
            <option value="MISSING">Missing</option>
          </select>
        </div>
      </div>

      {/* Alert Cards Grid */}
      {loading ? (
        <div className="flex flex-col items-center justify-center p-12 text-gray-400">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-2" />
          <span className="text-xs">Loading operational alerts...</span>
        </div>
      ) : alerts.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg p-12 text-center text-gray-500 space-y-2">
          <Bell className="w-10 h-10 text-gray-300 mx-auto" />
          <h3 className="text-base font-bold text-gray-700">No Operational Alerts Found</h3>
          <p className="text-xs text-gray-400 max-w-md mx-auto">
            Operational alerts are generated exclusively when an authorized examiner confirms a match in Module 8.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {alerts.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 text-xs border border-gray-300 rounded-md bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-xs text-gray-500 font-medium">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 text-xs border border-gray-300 rounded-md bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
