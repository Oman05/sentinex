/**
 * ModelStatus – Displays a single model version card with status badge.
 */

import { Cpu, CheckCircle2, FlaskConical, XCircle, Calendar, Database } from 'lucide-react';
import type { ModelRegistryItem } from '../types/analytics';

interface ModelStatusProps {
  model: ModelRegistryItem;
  onActivate?: (id: number) => void;
  onRetire?: (id: number) => void;
  isAdmin?: boolean;
}

const statusConfig = {
  ACTIVE:  { label: 'Active',   icon: CheckCircle2, color: 'text-green-600', bg: 'bg-green-50',  border: 'border-green-200' },
  TESTING: { label: 'Testing',  icon: FlaskConical,  color: 'text-yellow-600', bg: 'bg-yellow-50', border: 'border-yellow-200' },
  RETIRED: { label: 'Retired',  icon: XCircle,       color: 'text-gray-400',   bg: 'bg-gray-50',   border: 'border-gray-200' },
};

export default function ModelStatus({ model, onActivate, onRetire, isAdmin = false }: ModelStatusProps) {
  const config = statusConfig[model.status] ?? statusConfig.RETIRED;
  const StatusIcon = config.icon;

  return (
    <div className={`bg-white rounded-xl border-2 ${config.border} p-4 shadow-sm`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-lg ${config.bg}`}>
            <Cpu className={`w-4 h-4 ${config.color}`} />
          </div>
          <div>
            <p className="text-sm font-bold text-gray-800">{model.model_name}</p>
            <p className="text-xs text-gray-500">{model.model_type}</p>
          </div>
        </div>
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${config.bg} ${config.color} ${config.border} border`}>
          <StatusIcon className="w-3 h-3" />
          {config.label}
        </span>
      </div>

      {/* Details */}
      <div className="space-y-1.5 text-xs text-gray-500">
        <div className="flex justify-between">
          <span className="font-medium text-gray-600">Version</span>
          <code className="font-mono text-gray-700 bg-gray-100 px-1.5 py-0.5 rounded">{model.version}</code>
        </div>
        {model.framework && (
          <div className="flex justify-between">
            <span className="font-medium text-gray-600">Framework</span>
            <span>{model.framework}</span>
          </div>
        )}
        {model.dataset_version && (
          <div className="flex justify-between">
            <span className="font-medium text-gray-600">Dataset</span>
            <span className="flex items-center gap-1"><Database className="w-3 h-3" />{model.dataset_version}</span>
          </div>
        )}
        {model.deployed_at && (
          <div className="flex justify-between">
            <span className="font-medium text-gray-600">Deployed</span>
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {new Date(model.deployed_at).toLocaleDateString()}
            </span>
          </div>
        )}
        {model.retired_at && (
          <div className="flex justify-between">
            <span className="font-medium text-gray-600">Retired</span>
            <span>{new Date(model.retired_at).toLocaleDateString()}</span>
          </div>
        )}
      </div>

      {/* Notes */}
      {model.notes && (
        <p className="mt-2 text-xs text-gray-400 italic leading-snug">{model.notes}</p>
      )}

      {/* Admin actions */}
      {isAdmin && (
        <div className="mt-3 flex gap-2">
          {model.status === 'TESTING' && onActivate && (
            <button
              onClick={() => onActivate(model.id)}
              className="flex-1 text-xs font-medium px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors"
            >
              Activate
            </button>
          )}
          {model.status === 'ACTIVE' && onRetire && (
            <button
              onClick={() => onRetire(model.id)}
              className="flex-1 text-xs font-medium px-3 py-1.5 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-md transition-colors"
            >
              Retire
            </button>
          )}
        </div>
      )}
    </div>
  );
}
