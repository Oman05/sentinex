import { useEffect, useState } from "react";
import {
  Bell,
  Mail,
  Smartphone,
  Server,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import type { AlertNotification } from '../types/alert';
import { getAlertNotifications, retryAlertNotifications } from '../services/alertApi';
import { AlertStatusBadge } from '../components/AlertStatus';
import { format, parseISO } from 'date-fns';

export default function NotificationHistory() {
  const [notifications, setNotifications] = useState<AlertNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [retryingId, setRetryingId] = useState<number | null>(null);

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      // Fetch notifications across active alerts (or for demo alert 1)
      const res = await getAlertNotifications(1).catch(() => []);
      setNotifications(res);
    } catch (err) {
      console.error('Failed to load notification history', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, []);

  const handleRetry = async (alertId: number, notifId: number) => {
    try {
      setRetryingId(notifId);
      await retryAlertNotifications(alertId, notifId);
      await fetchNotifications();
    } catch (err) {
      console.error('Retry failed', err);
    } finally {
      setRetryingId(null);
    }
  };

  const getChannelIcon = (channel: string) => {
    switch (channel) {
      case 'EMAIL':
        return <Mail className="w-4 h-4 text-sky-600" />;
      case 'SMS':
        return <Smartphone className="w-4 h-4 text-emerald-600" />;
      case 'PUSH_NOTIFICATION':
        return <Bell className="w-4 h-4 text-purple-600" />;
      case 'SECURE_INTERNAL_API':
        return <Server className="w-4 h-4 text-indigo-600" />;
      default:
        return <Bell className="w-4 h-4 text-blue-600" />;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-2">
            <Bell className="w-6 h-6 text-blue-600" />
            Notification Delivery History &amp; Channels
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Tracking delivery statuses across In-App, Email, SMS, and secure gateway adapters.
          </p>
        </div>

        <button
          onClick={fetchNotifications}
          disabled={loading}
          className="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-xs font-semibold px-3 py-2 rounded-md shadow-sm flex items-center gap-1.5 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Deliveries
        </button>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center p-12 text-gray-400">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-2" />
          <span className="text-xs">Loading transmission history...</span>
        </div>
      ) : notifications.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg p-12 text-center text-gray-500 space-y-2">
          <Bell className="w-10 h-10 text-gray-300 mx-auto" />
          <h3 className="text-base font-bold text-gray-700">No Notifications Dispatched Yet</h3>
          <p className="text-xs text-gray-400 max-w-md mx-auto">
            Dispatches appear here automatically when Module 9 routes operational alerts to department endpoints.
          </p>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
          <table className="min-w-full divide-y divide-gray-200 text-xs">
            <thead className="bg-gray-50 text-gray-500 font-semibold uppercase tracking-wider text-[11px]">
              <tr>
                <th className="px-4 py-3 text-left">Channel</th>
                <th className="px-4 py-3 text-left">Alert ID</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Attempts</th>
                <th className="px-4 py-3 text-left">Delivered Timestamp</th>
                <th className="px-4 py-3 text-left">Details</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 text-gray-700">
              {notifications.map((n) => (
                <tr key={n.id} className="hover:bg-gray-50/80 transition-colors">
                  <td className="px-4 py-3 font-semibold flex items-center gap-2">
                    {getChannelIcon(n.channel)}
                    {n.channel.replace(/_/g, ' ')}
                  </td>
                  <td className="px-4 py-3 font-mono font-medium text-gray-900">
                    #{n.alert_id}
                  </td>
                  <td className="px-4 py-3">
                    <AlertStatusBadge status={n.status} size="sm" />
                  </td>
                  <td className="px-4 py-3 font-mono">{n.attempt_count}</td>
                  <td className="px-4 py-3 font-mono text-gray-500">
                    {n.delivered_at
                      ? format(parseISO(n.delivered_at), 'yyyy-MM-dd HH:mm:ss')
                      : 'Pending'}
                  </td>
                  <td className="px-4 py-3 text-gray-500 max-w-xs truncate">
                    {n.error_message || n.message_payload || 'Normal delivery'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {n.status === 'FAILED' && (
                      <button
                        onClick={() => handleRetry(n.alert_id, n.id)}
                        disabled={retryingId === n.id}
                        className="bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 px-2.5 py-1 rounded text-xs font-semibold disabled:opacity-50"
                      >
                        {retryingId === n.id ? 'Retrying...' : 'Retry'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
