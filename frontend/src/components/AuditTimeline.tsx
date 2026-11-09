import React from 'react';
import { format } from 'date-fns';
import { Lock, FileText, CheckCircle, AlertOctagon, HelpCircle, UserPlus, PlayCircle, Shield, Download, Eye, Archive, Trash2 } from 'lucide-react';
import type { ReviewAuditEntry } from '../types/review';
import type { AuditLogItem } from '../types/evidence';

interface AuditTimelineProps {
  entries?: ReviewAuditEntry[];
  auditLogs?: AuditLogItem[];
  isLoading?: boolean;
}

export const AuditTimeline: React.FC<AuditTimelineProps> = ({ entries, auditLogs, isLoading }) => {
  if (isLoading) {
    return <div className="p-8 text-center text-gray-500 animate-pulse">Loading audit log...</div>;
  }

  // Handle SystemAuditLog items (Module 10)
  if (auditLogs && auditLogs.length > 0) {
    const getSystemIcon = (action: string) => {
      if (action.includes('VIEW')) return <Eye className="w-4 h-4 text-blue-500" />;
      if (action.includes('DOWNLOAD') || action.includes('EXPORT')) return <Download className="w-4 h-4 text-amber-500" />;
      if (action.includes('ARCHIVE')) return <Archive className="w-4 h-4 text-purple-500" />;
      if (action.includes('DELETE')) return <Trash2 className="w-4 h-4 text-red-500" />;
      if (action.includes('CREATE')) return <CheckCircle className="w-4 h-4 text-green-500" />;
      return <Shield className="w-4 h-4 text-gray-500" />;
    };

    return (
      <div className="bg-white rounded-lg shadow border border-gray-200">
        <div className="border-b border-gray-200 px-4 py-3 bg-gray-50 rounded-t-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-gray-500" />
            <h3 className="text-sm font-semibold text-gray-800">System Audit Trail</h3>
          </div>
          <span className="text-xs text-gray-500">Immutable Ledger</span>
        </div>
        <div className="p-6">
          <div className="relative border-l-2 border-gray-200 ml-3 space-y-6">
            {auditLogs.map((log) => (
              <div key={log.id} className="relative pl-6">
                <div className="absolute -left-[11px] bg-white p-0.5 rounded-full border-2 border-white shadow-sm">
                  {getSystemIcon(log.action)}
                </div>
                <div>
                  <div className="flex items-baseline justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-900 text-sm">
                        {log.actor_username || 'SYSTEM'}
                      </span>
                      <span className="font-mono text-xs text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                        {log.event_id}
                      </span>
                    </div>
                    <span className="text-xs text-gray-500 font-mono">
                      {format(new Date(log.timestamp), 'PP pp')}
                    </span>
                  </div>

                  <div className="p-3 bg-gray-50 rounded border border-gray-200 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-gray-800">{log.action}</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${log.result === 'SUCCESS' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        {log.result}
                      </span>
                    </div>
                    <div className="text-gray-600 mt-1">
                      Resource: <strong className="text-gray-900 font-mono">{log.resource_type}</strong>{' '}
                      {log.resource_label && <span>({log.resource_label})</span>}
                    </div>
                    {log.reason && (
                      <div className="mt-1.5 text-gray-700 italic bg-white p-1.5 rounded border border-gray-100">
                        Reason: "{log.reason}"
                      </div>
                    )}
                    {log.ip_address && (
                      <div className="mt-1 text-[10px] text-gray-400 font-mono">
                        IP: {log.ip_address}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Handle ReviewAuditEntry items (Module 8 backwards compatibility)
  if (!entries || entries.length === 0) {
    return <div className="p-8 text-center text-gray-500 border rounded bg-gray-50">No audit history available.</div>;
  }

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'START_REVIEW': return <PlayCircle className="w-5 h-5 text-blue-500" />;
      case 'CONFIRM_FOR_ACTION': return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'REJECTED': return <AlertOctagon className="w-5 h-5 text-red-500" />;
      case 'NEED_MORE_EVIDENCE': return <HelpCircle className="w-5 h-5 text-amber-500" />;
      case 'ASSIGN': return <UserPlus className="w-5 h-5 text-gray-500" />;
      case 'EVIDENCE_REQUEST': return <FileText className="w-5 h-5 text-purple-500" />;
      default: return <FileText className="w-5 h-5 text-gray-400" />;
    }
  };

  const getActionColor = (action: string) => {
    switch (action) {
      case 'START_REVIEW': return 'bg-blue-50 border-blue-200 text-blue-700';
      case 'CONFIRM_FOR_ACTION': return 'bg-green-50 border-green-200 text-green-800';
      case 'REJECTED': return 'bg-red-50 border-red-200 text-red-800';
      case 'NEED_MORE_EVIDENCE': return 'bg-amber-50 border-amber-200 text-amber-800';
      case 'EVIDENCE_REQUEST': return 'bg-purple-50 border-purple-200 text-purple-800';
      default: return 'bg-gray-50 border-gray-200 text-gray-700';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200">
      <div className="border-b border-gray-200 px-4 py-3 bg-gray-50 rounded-t-lg flex items-center gap-2">
        <Lock className="w-4 h-4 text-gray-500" />
        <h3 className="text-sm font-semibold text-gray-800">Append-only Audit Log</h3>
        <span className="text-xs text-gray-500 ml-auto">Immutable Record</span>
      </div>
      
      <div className="p-6">
        <div className="relative border-l-2 border-gray-200 ml-3 space-y-8">
          {entries.map((entry, index) => (
            <div key={entry.id || index} className="relative pl-6">
              <div className="absolute -left-[11px] bg-white p-0.5 rounded-full border-2 border-white">
                {getActionIcon(entry.action)}
              </div>
              
              <div>
                <div className="flex items-baseline justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-900 text-sm">
                      {entry.actor_username || `Officer ${entry.actor_id}`}
                    </span>
                    <span className="text-gray-500 text-sm">recorded action</span>
                  </div>
                  <span className="text-xs text-gray-500 font-mono">
                    {format(new Date(entry.timestamp), 'PP pp')}
                  </span>
                </div>
                
                <div className={`mt-2 p-3 rounded-md border text-sm ${getActionColor(entry.action)}`}>
                  <div className="font-semibold mb-1">{entry.action.replace(/_/g, ' ')}</div>
                  {entry.notes && (
                    <div className="mt-2 text-gray-700 bg-white bg-opacity-50 p-2 rounded border border-gray-100 italic">
                      "{entry.notes}"
                    </div>
                  )}
                  {entry.previous_status && entry.new_status && entry.previous_status !== entry.new_status && (
                    <div className="mt-2 text-xs flex items-center gap-2 opacity-80">
                      <span>Status changed:</span>
                      <span className="line-through">{entry.previous_status}</span>
                      <span>&rarr;</span>
                      <span className="font-bold">{entry.new_status}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
