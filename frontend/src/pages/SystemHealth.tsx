/**
 * SystemHealth – Module 11 live system health monitoring page.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Activity, Camera, Cpu, Database, RefreshCw,
  CheckCircle2, XCircle, AlertTriangle, Wifi, WifiOff,
} from 'lucide-react';
import MetricCard from '../components/MetricCard';
import { getSystemHealth, getCameraAnalytics, getTechnicalAlerts } from '../services/analyticsApi';
import type { SystemHealthResponse, CameraAnalyticsItem, AnalyticsAlertItem } from '../types/analytics';

const severityColor: Record<string, string> = {
  INFO:     'text-blue-600 bg-blue-50 border-blue-200',
  WARNING:  'text-yellow-600 bg-yellow-50 border-yellow-200',
  CRITICAL: 'text-red-600 bg-red-50 border-red-200',
};

export default function SystemHealth() {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [cameras, setCameras] = useState<CameraAnalyticsItem[]>([]);
  const [techAlerts, setTechAlerts] = useState<AnalyticsAlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isAdmin] = useState(() => {
    try {
      const token = localStorage.getItem('sentinex_token');
      if (!token) return false;
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.role === 'ADMIN';
    } catch { return false; }
  });

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [h, cams] = await Promise.all([
        getSystemHealth(),
        getCameraAnalytics('today'),
      ]);
      setHealth(h);
      setCameras(cams);
      if (isAdmin) {
        const alerts = await getTechnicalAlerts(false);
        setTechAlerts(alerts);
      }
    } catch { /* silent */ }
    setLoading(false);
  }, [isAdmin]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  // Auto-refresh every 60s
  useEffect(() => {
    const iv = setInterval(fetchAll, 60_000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Activity className="w-6 h-6 text-green-600" />
            System Health
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Live system infrastructure and AI pipeline health metrics.
          </p>
        </div>
        <button
          onClick={fetchAll}
          disabled={loading}
          className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Overall status banner */}
      {health && (
        <div className={`rounded-xl border-2 p-4 flex items-center gap-3 ${
          !health.db_healthy || health.cameras_error > 0
            ? 'bg-red-50 border-red-200'
            : health.cameras_offline > 0
            ? 'bg-yellow-50 border-yellow-200'
            : 'bg-green-50 border-green-200'
        }`}>
          {!health.db_healthy || health.cameras_error > 0
            ? <XCircle className="w-6 h-6 text-red-500" />
            : health.cameras_offline > 0
            ? <AlertTriangle className="w-6 h-6 text-yellow-500" />
            : <CheckCircle2 className="w-6 h-6 text-green-500" />
          }
          <div>
            <p className="font-semibold text-gray-800">
              {!health.db_healthy ? 'Database Error Detected' :
               health.cameras_error > 0 ? `${health.cameras_error} Camera(s) in Error State` :
               health.cameras_offline > 0 ? `${health.cameras_offline} Camera(s) Offline` :
               'All Systems Operational'}
            </p>
            <p className="text-xs text-gray-500">
              Last updated: {new Date().toLocaleTimeString()} · Auto-refreshes every 60s
            </p>
          </div>
        </div>
      )}

      {/* Key metrics */}
      {health && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3">
          <MetricCard label="DB Status"
            value={health.db_healthy ? 'Healthy' : 'Error'}
            icon={health.db_healthy ? Database : XCircle}
            color={health.db_healthy ? 'green' : 'red'}
          />
          <MetricCard label="Cameras Online"  value={health.cameras_online}  icon={Wifi}    color="green" />
          <MetricCard label="Cameras Offline" value={health.cameras_offline} icon={WifiOff} color={health.cameras_offline > 0 ? 'yellow' : 'gray'} />
          <MetricCard label="Cameras Error"   value={health.cameras_error}   icon={Camera}  color={health.cameras_error > 0 ? 'red' : 'gray'} />
          <MetricCard label="Frames (24h)"    value={health.frames_received.toLocaleString()} icon={Cpu} color="blue" />
          <MetricCard label="Processed"       value={health.frames_processed.toLocaleString()} color="green" />
          <MetricCard label="Dropped"         value={health.frames_dropped.toLocaleString()} color={health.frames_dropped > 0 ? 'red' : 'gray'} />
          <MetricCard label="Avg Latency"
            value={health.avg_latency_ms !== null ? `${health.avg_latency_ms.toFixed(1)}` : '—'}
            suffix="ms"
            color="blue"
            description="Processing latency"
          />
          {health.queue_size !== null && (
            <MetricCard label="Queue Size" value={health.queue_size} color={health.queue_size > 100 ? 'yellow' : 'gray'} />
          )}
        </div>
      )}

      {/* Camera table */}
      <section>
        <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
          <Camera className="w-4 h-4" /> Camera Status (Today)
        </h2>
        {cameras.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center text-gray-400 text-sm">
            No camera data available.
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    {['Camera', 'Frames Rcvd', 'Processed', 'Dropped', 'Detections', 'Face Candidates', 'Avg Latency', 'Errors'].map((h) => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {cameras.map((cam) => (
                    <tr key={cam.camera_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-800">{cam.camera_name}</p>
                        <p className="text-xs text-gray-400">ID: {cam.camera_id}</p>
                      </td>
                      <td className="px-4 py-3 text-gray-700">{cam.frames_received.toLocaleString()}</td>
                      <td className="px-4 py-3 text-green-700 font-medium">{cam.frames_processed.toLocaleString()}</td>
                      <td className="px-4 py-3">
                        <span className={cam.frames_dropped > 0 ? 'text-red-600 font-medium' : 'text-gray-400'}>
                          {cam.frames_dropped.toLocaleString()}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-blue-700">{cam.detections.toLocaleString()}</td>
                      <td className="px-4 py-3 text-purple-700">{cam.face_candidates.toLocaleString()}</td>
                      <td className="px-4 py-3 text-gray-600">
                        {cam.avg_latency_ms !== null ? `${cam.avg_latency_ms.toFixed(1)} ms` : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <span className={cam.error_count > 0 ? 'text-red-600 font-semibold' : 'text-gray-300'}>
                          {cam.error_count}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* Technical Alerts (admin only) */}
      {isAdmin && techAlerts.length > 0 && (
        <section>
          <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> Technical System Alerts
          </h2>
          <p className="text-xs text-gray-400 mb-3 italic">
            These are infrastructure monitoring alerts, separate from Module 9 operational alerts.
          </p>
          <div className="space-y-2">
            {techAlerts.map((alert) => (
              <div key={alert.id} className={`rounded-lg border p-3 ${severityColor[alert.severity] ?? severityColor.INFO}`}>
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-sm">{alert.title}</p>
                  <span className="text-xs font-bold">{alert.alert_type.replace(/_/g, ' ')}</span>
                </div>
                {alert.description && <p className="text-xs mt-1 opacity-80">{alert.description}</p>}
                <p className="text-xs mt-1 opacity-60">
                  Detected: {new Date(alert.detected_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
