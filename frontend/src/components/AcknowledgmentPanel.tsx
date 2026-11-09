import React, { useState } from 'react';
import { CheckCircle2, PlayCircle, CheckSquare, XCircle, AlertCircle, Loader2 } from 'lucide-react';
import type { AlertDetail, AlertStatus } from '../types/alert';
import { acknowledgeAlert, updateAlertStatus } from '../services/alertApi';

interface AcknowledgmentPanelProps {
  alert: AlertDetail;
  onAlertUpdated: (updated: AlertDetail) => void;
}

export const AcknowledgmentPanel: React.FC<AcknowledgmentPanelProps> = ({
  alert,
  onAlertUpdated,
}) => {
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAcknowledge = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await acknowledgeAlert(alert.id, notes);
      onAlertUpdated(res);
      setNotes('');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to acknowledge alert');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (targetStatus: AlertStatus) => {
    try {
      setLoading(true);
      setError(null);
      const res = await updateAlertStatus(alert.id, targetStatus, notes);
      onAlertUpdated(res);
      setNotes('');
    } catch (err: any) {
      setError(err?.response?.data?.detail || `Failed to update status to ${targetStatus}`);
    } finally {
      setLoading(false);
    }
  };

  const isAcknowledged =
    alert.status === 'ACKNOWLEDGED' ||
    alert.status === 'IN_PROGRESS' ||
    alert.status === 'RESOLVED' ||
    alert.status === 'CLOSED';

  const isClosed = alert.status === 'CLOSED' || alert.status === 'RESOLVED';

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm space-y-4">
      <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider flex items-center gap-2 border-b border-gray-100 pb-2">
        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
        Operational Actions &amp; Lifecycle
      </h3>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-xs p-3 rounded-md flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Notes input */}
      {!isClosed && (
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            Officer Notes / Action Plan:
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Enter operational notes, unit dispatch numbers, or case findings..."
            rows={2}
            className="w-full text-xs border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none"
          />
        </div>
      )}

      {/* Buttons */}
      <div className="flex flex-wrap gap-2 pt-1">
        {!isAcknowledged && (
          <button
            onClick={handleAcknowledge}
            disabled={loading}
            className="bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs px-4 py-2 rounded-md transition-colors flex items-center gap-1.5 shadow-sm disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
            Acknowledge Alert
          </button>
        )}

        {alert.status === 'ACKNOWLEDGED' && (
          <button
            onClick={() => handleStatusChange('IN_PROGRESS')}
            disabled={loading}
            className="bg-purple-600 hover:bg-purple-700 text-white font-semibold text-xs px-4 py-2 rounded-md transition-colors flex items-center gap-1.5 shadow-sm disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlayCircle className="w-3.5 h-3.5" />}
            Begin Field Action (In Progress)
          </button>
        )}

        {alert.status === 'IN_PROGRESS' && (
          <button
            onClick={() => handleStatusChange('RESOLVED')}
            disabled={loading}
            className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs px-4 py-2 rounded-md transition-colors flex items-center gap-1.5 shadow-sm disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckSquare className="w-3.5 h-3.5" />}
            Mark Incident Resolved
          </button>
        )}

        {!isClosed && (
          <button
            onClick={() => handleStatusChange('CLOSED')}
            disabled={loading}
            className="bg-gray-700 hover:bg-gray-800 text-white font-semibold text-xs px-4 py-2 rounded-md transition-colors flex items-center gap-1.5 shadow-sm disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5" />}
            Close Alert
          </button>
        )}

        {isClosed && (
          <div className="text-xs text-gray-500 italic bg-gray-50 p-2.5 rounded border border-gray-200 w-full text-center">
            This alert has been {alert.status.toLowerCase()} and is closed for further operational transitions.
          </div>
        )}
      </div>
    </div>
  );
};
