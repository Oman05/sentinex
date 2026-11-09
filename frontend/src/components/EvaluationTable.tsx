/**
 * EvaluationTable – Table of evaluation runs with status and action buttons.
 */

import { Play, Eye, Clock, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import type { EvaluationRunItem } from '../types/analytics';

interface EvaluationTableProps {
  runs: EvaluationRunItem[];
  onExecute?: (runId: string) => void;
  onViewResults?: (runId: string) => void;
  isLoading?: boolean;
}

const statusConfig = {
  PENDING:   { label: 'Pending',    Icon: Clock,        color: 'text-gray-500',   bg: 'bg-gray-100'   },
  RUNNING:   { label: 'Running',    Icon: Loader2,      color: 'text-blue-600',   bg: 'bg-blue-50'    },
  COMPLETED: { label: 'Completed',  Icon: CheckCircle2, color: 'text-green-600',  bg: 'bg-green-50'   },
  FAILED:    { label: 'Failed',     Icon: XCircle,      color: 'text-red-600',    bg: 'bg-red-50'     },
};

export default function EvaluationTable({ runs, onExecute, onViewResults, isLoading }: EvaluationTableProps) {
  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-8 text-center shadow-sm">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500 mx-auto mb-2" />
        <p className="text-sm text-gray-500">Loading evaluation runs…</p>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-8 text-center shadow-sm">
        <p className="text-sm text-gray-400">No evaluation runs found. Create one to begin.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Run ID</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Model</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Dataset</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Threshold</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Created</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {runs.map((run) => {
              const sc = statusConfig[run.status] ?? statusConfig.PENDING;
              const StatusIcon = sc.Icon;
              return (
                <tr key={run.run_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <code className="text-xs font-mono text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
                      {run.run_id}
                    </code>
                    {run.run_name && (
                      <p className="text-xs text-gray-400 mt-0.5">{run.run_name}</p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-800">{run.model_name}</p>
                    <p className="text-xs text-gray-400">v{run.model_version}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-800">{run.dataset_name}</p>
                    <p className="text-xs text-gray-400">v{run.dataset_version}</p>
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {run.threshold !== null ? run.threshold?.toFixed(2) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${sc.bg} ${sc.color}`}>
                      <StatusIcon className={`w-3 h-3 ${run.status === 'RUNNING' ? 'animate-spin' : ''}`} />
                      {sc.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {new Date(run.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      {run.status === 'PENDING' && onExecute && (
                        <button
                          onClick={() => onExecute(run.run_id)}
                          className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors"
                        >
                          <Play className="w-3 h-3" /> Execute
                        </button>
                      )}
                      {run.status === 'COMPLETED' && onViewResults && (
                        <button
                          onClick={() => onViewResults(run.run_id)}
                          className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors"
                        >
                          <Eye className="w-3 h-3" /> Results
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
