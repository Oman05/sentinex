import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Users,
  Building2,
  Camera,
  Activity,
  ShieldCheck,
  Server,
  Database,
  HardDrive,
  Cpu,
  AlertTriangle,
  RotateCw,
  Sliders,
  Archive,
  History,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { getAdminDashboard } from '../services/adminApi';
import type { AdminDashboardMetrics } from '../types/admin';

export default function AdminDashboard() {
  const [metrics, setMetrics] = useState<AdminDashboardMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAdminDashboard();
      setMetrics(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load admin metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !metrics) {
    return (
      <div className="flex h-full items-center justify-center">
        <RotateCw className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-2">
            <ShieldCheck className="w-7 h-7 text-blue-600" />
            Admin &amp; System Management Control Center
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Module 12: Centralized administrative governance, RBAC, camera streams, AI configuration, and subsystem telemetry.
          </p>
        </div>
        <button
          onClick={fetchMetrics}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition"
        >
          <RotateCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Status
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md text-sm">
          {error}
        </div>
      )}

      {/* Subsystem Health Ribbon */}
      {metrics && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
          {[
            { label: 'Overall System', val: metrics.system_health, icon: Activity },
            { label: 'AI Inference', val: metrics.ai_model_status, icon: Cpu },
            { label: 'Database', val: metrics.database_status, icon: Database },
            { label: 'Storage & Vault', val: metrics.storage_status, icon: HardDrive },
            { label: 'Background Workers', val: metrics.worker_status, icon: Server },
            { label: 'Active Alerts', val: `${metrics.active_alerts} Active`, icon: AlertTriangle },
          ].map((item, idx) => {
            const isOk = item.val.toLowerCase().includes('health') || item.val.toLowerCase().includes('ok') || typeof item.val === 'string' && !item.val.includes('degraded');
            return (
              <div key={idx} className="bg-white p-3 rounded-lg border border-gray-200 shadow-sm flex items-center space-x-3">
                <div className={`p-2 rounded-md ${isOk ? 'bg-green-50 text-green-600' : 'bg-amber-50 text-amber-600'}`}>
                  <item.icon className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs text-gray-500">{item.label}</div>
                  <div className="text-sm font-semibold capitalize text-gray-800 flex items-center gap-1">
                    {item.val}
                    {isOk ? <CheckCircle2 className="w-3.5 h-3.5 text-green-500 inline" /> : <XCircle className="w-3.5 h-3.5 text-amber-500 inline" />}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        {[
          { label: 'User Directory', path: '/admin/users', icon: Users, desc: `${metrics?.total_users ?? 0} Users` },
          { label: 'Departments', path: '/admin/departments', icon: Building2, desc: `${metrics?.active_departments ?? 0} Active` },
          { label: 'CCTV Cameras', path: '/admin/cameras', icon: Camera, desc: `${metrics?.online_cameras ?? 0}/${metrics?.registered_cameras ?? 0} Online` },
          { label: 'System Config', path: '/admin/config', icon: Sliders, desc: 'Tuning & Gates' },
          { label: 'Worker Monitor', path: '/admin/workers', icon: Server, desc: 'Task Queues' },
          { label: 'Backups Vault', path: '/admin/backups', icon: Archive, desc: 'SHA-256 Verified' },
          { label: 'System Audits', path: '/admin/audit', icon: History, desc: 'Full Trail' },
        ].map((btn, idx) => (
          <Link
            key={idx}
            to={btn.path}
            className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm hover:border-blue-500 hover:shadow-md transition text-center flex flex-col items-center group"
          >
            <div className="p-3 bg-blue-50 text-blue-600 rounded-full group-hover:bg-blue-600 group-hover:text-white transition mb-2">
              <btn.icon className="w-5 h-5" />
            </div>
            <span className="text-sm font-medium text-gray-800">{btn.label}</span>
            <span className="text-xs text-gray-500 mt-0.5">{btn.desc}</span>
          </Link>
        ))}
      </div>

      {/* Core Operational Statistics */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Active Investigations</span>
            <div className="text-2xl font-bold text-gray-900 mt-2">{metrics.active_cases}</div>
            <div className="text-xs text-gray-500 mt-1">Controlled missing/wanted cases</div>
          </div>

          <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Pending Human Reviews</span>
            <div className="text-2xl font-bold text-amber-600 mt-2">{metrics.pending_human_reviews}</div>
            <div className="text-xs text-amber-600 mt-1 font-medium">Mandatory verification required</div>
          </div>

          <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Confirmed for Action</span>
            <div className="text-2xl font-bold text-green-600 mt-2">{metrics.confirmed_for_action_events}</div>
            <div className="text-xs text-gray-500 mt-1">Human-approved matches</div>
          </div>

          <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Active Alert Pipelines</span>
            <div className="text-2xl font-bold text-blue-600 mt-2">{metrics.active_alerts}</div>
            <div className="text-xs text-gray-500 mt-1">Multi-channel department dispatches</div>
          </div>
        </div>
      )}

      {/* Recent Security & Administrative Activity */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
            <History className="w-5 h-5 text-gray-500" />
            Recent Administrative &amp; Security Events
          </h2>
          <Link to="/admin/audit" className="text-xs font-medium text-blue-600 hover:text-blue-700">
            View Complete Audit Log &rarr;
          </Link>
        </div>

        <div className="divide-y divide-gray-100">
          {metrics?.recent_security_events && metrics.recent_security_events.length > 0 ? (
            metrics.recent_security_events.map((evt) => (
              <div key={evt.id} className="px-6 py-3 text-sm flex items-center justify-between hover:bg-gray-50">
                <div className="flex items-center space-x-3">
                  <span className="px-2 py-0.5 text-xs font-medium rounded bg-gray-100 text-gray-800">
                    {evt.action}
                  </span>
                  <span className="text-gray-700">{evt.details || `${evt.resource_type} #${evt.resource_id}`}</span>
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(evt.timestamp).toLocaleString()}
                </span>
              </div>
            ))
          ) : (
            <div className="p-6 text-center text-sm text-gray-500">
              No recent security logs recorded.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
