import React from 'react';
import { Clock, Shield, CheckCircle, FileText, Camera, AlertCircle, Eye, Download, Archive, User } from 'lucide-react';
import type { TimelineEntry } from '../types/evidence';

interface EvidenceTimelineProps {
  entries: TimelineEntry[];
  evidenceId: string;
  caseNumber?: string | null;
  isLoading?: boolean;
}

export const EvidenceTimeline: React.FC<EvidenceTimelineProps> = ({
  entries,
  evidenceId,
  caseNumber,
  isLoading,
}) => {
  if (isLoading) {
    return (
      <div className="p-8 text-center text-gray-400 animate-pulse">
        <Clock className="w-8 h-8 mx-auto mb-2 animate-spin text-blue-500" />
        <span>Synthesizing chronological audit events...</span>
      </div>
    );
  }

  if (!entries || entries.length === 0) {
    return (
      <div className="p-8 text-center text-gray-500 bg-gray-50 rounded-lg border border-gray-200">
        No lifecycle audit entries recorded yet for {evidenceId}.
      </div>
    );
  }

  const getActionIcon = (action: string) => {
    if (action.includes('CAPTURE') || action.includes('FRAME')) return <Camera className="w-4 h-4 text-blue-500" />;
    if (action.includes('DETECTION') || action.includes('MATCH')) return <Shield className="w-4 h-4 text-cyan-500" />;
    if (action.includes('REVIEW')) return <CheckCircle className="w-4 h-4 text-emerald-500" />;
    if (action.includes('ALERT')) return <AlertCircle className="w-4 h-4 text-rose-500" />;
    if (action.includes('VIEW')) return <Eye className="w-4 h-4 text-indigo-500" />;
    if (action.includes('DOWNLOAD') || action.includes('EXPORT')) return <Download className="w-4 h-4 text-amber-500" />;
    if (action.includes('ARCHIVE')) return <Archive className="w-4 h-4 text-purple-500" />;
    return <FileText className="w-4 h-4 text-gray-500" />;
  };

  const getActionBadgeColor = (action: string) => {
    if (action.includes('ALERT') || action.includes('FAIL')) return 'bg-rose-50 text-rose-700 border-rose-200';
    if (action.includes('REVIEW') || action.includes('VERIFIED')) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    if (action.includes('DOWNLOAD') || action.includes('EXPORT')) return 'bg-amber-50 text-amber-700 border-amber-200';
    if (action.includes('CREATE') || action.includes('CAPTURE')) return 'bg-blue-50 text-blue-700 border-blue-200';
    return 'bg-gray-50 text-gray-700 border-gray-200';
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
            <Clock className="w-4 h-4 text-blue-600" />
            Immutable Chronological Lifecycle Timeline
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Derived directly from cryptographic audit ledger entries for {evidenceId}
            {caseNumber ? ` (Case ${caseNumber})` : ''}
          </p>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 bg-blue-100 text-blue-800 rounded-full">
          {entries.length} Ledger Events
        </span>
      </div>

      {/* Timeline Stream */}
      <div className="p-6">
        <div className="relative border-l-2 border-gray-200 ml-4 space-y-6">
          {entries.map((entry, index) => (
            <div key={index} className="relative pl-6">
              {/* Dot Icon */}
              <div className="absolute -left-[17px] top-0 bg-white p-1 rounded-full border-2 border-gray-300 shadow-sm">
                {getActionIcon(entry.action)}
              </div>

              {/* Event Content */}
              <div className="bg-gray-50/70 hover:bg-gray-50 p-3.5 rounded-lg border border-gray-100 transition-colors">
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${getActionBadgeColor(entry.action)}`}>
                    {entry.action}
                  </span>
                  <span className="font-mono text-xs font-semibold text-gray-600">
                    {new Date(entry.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    <span className="text-gray-400 font-normal ml-1">
                      {new Date(entry.timestamp).toLocaleDateString()}
                    </span>
                  </span>
                </div>

                <div className="text-xs text-gray-800 font-medium mb-1">
                  {entry.description}
                </div>

                <div className="flex items-center gap-4 text-[11px] text-gray-500 mt-2 pt-2 border-t border-gray-200/60">
                  <span className="flex items-center gap-1">
                    <User className="w-3 h-3 text-gray-400" />
                    Actor: <strong className="text-gray-700">{entry.actor || 'SYSTEM'}</strong>
                  </span>
                  {entry.resource_id && (
                    <span>
                      Ref: <strong className="text-gray-700 font-mono">{entry.resource_id}</strong>
                    </span>
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
