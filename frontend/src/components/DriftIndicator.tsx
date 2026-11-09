/**
 * DriftIndicator – Displays a drift event with severity badge and deviation.
 */

import { AlertTriangle, Info, XOctagon, CheckCircle2 } from 'lucide-react';
import type { DriftEventItem } from '../types/analytics';

interface DriftIndicatorProps {
  event: DriftEventItem;
  onAcknowledge?: (id: number) => void;
  isAdmin?: boolean;
}

const severityConfig = {
  INFO:     { label: 'Info',     Icon: Info,          bg: 'bg-blue-50',   border: 'border-blue-200',   text: 'text-blue-700'  },
  WARNING:  { label: 'Warning',  Icon: AlertTriangle, bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-700' },
  CRITICAL: { label: 'Critical', Icon: XOctagon,      bg: 'bg-red-50',    border: 'border-red-200',    text: 'text-red-700'   },
};

export default function DriftIndicator({ event, onAcknowledge, isAdmin = false }: DriftIndicatorProps) {
  const config = severityConfig[event.severity] ?? severityConfig.INFO;
  const { Icon } = config;

  return (
    <div className={`rounded-xl border-2 ${config.border} ${config.bg} p-4 shadow-sm`}>
      <div className="flex items-start gap-3">
        <Icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${config.text}`} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className={`text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${config.bg} ${config.text} border ${config.border}`}>
              {config.label} — {event.event_type.replace('_', ' ')}
            </span>
            {event.is_acknowledged && (
              <span className="text-xs text-green-600 font-medium flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Acknowledged
              </span>
            )}
          </div>

          <p className="mt-1.5 text-sm font-semibold text-gray-800">{event.metric_name.replace(/_/g, ' ')}</p>

          {event.description && (
            <p className="mt-1 text-xs text-gray-600 leading-snug">{event.description}</p>
          )}

          {/* Baseline vs Current */}
          {event.baseline_value !== null && event.current_value !== null && (
            <div className="mt-2 flex gap-4 text-xs">
              <div>
                <span className="text-gray-500 font-medium">Baseline: </span>
                <span className="font-bold text-gray-700">{event.baseline_value?.toFixed(4)}</span>
              </div>
              <div>
                <span className="text-gray-500 font-medium">Current: </span>
                <span className={`font-bold ${config.text}`}>{event.current_value?.toFixed(4)}</span>
              </div>
              {event.deviation !== null && (
                <div>
                  <span className="text-gray-500 font-medium">Δ </span>
                  <span className={`font-bold ${config.text}`}>{event.deviation?.toFixed(1)}%</span>
                </div>
              )}
            </div>
          )}

          <p className="mt-1.5 text-xs text-gray-400">
            Detected: {new Date(event.detected_at).toLocaleString()}
          </p>
        </div>

        {/* Acknowledge */}
        {isAdmin && !event.is_acknowledged && onAcknowledge && (
          <button
            onClick={() => onAcknowledge(event.id)}
            className="flex-shrink-0 text-xs font-medium px-3 py-1.5 bg-white border border-gray-300 hover:bg-gray-50 text-gray-600 rounded-md transition-colors"
          >
            Acknowledge
          </button>
        )}
      </div>
    </div>
  );
}
