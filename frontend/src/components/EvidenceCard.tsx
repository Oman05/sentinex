import React from 'react';
import { Camera, Film, FileText, Cpu, AlertCircle, CheckCircle2, XCircle, Clock } from 'lucide-react';
import type { EvidenceItem } from '../types/evidence';

interface EvidenceCardProps {
  item: EvidenceItem;
  onSelect: (item: EvidenceItem) => void;
  onViewTimeline?: (item: EvidenceItem) => void;
}

export const EvidenceCard: React.FC<EvidenceCardProps> = ({ item, onSelect, onViewTimeline }) => {
  const getTypeIcon = () => {
    if (item.evidence_type.includes('CLIP') || item.evidence_type.includes('VIDEO')) {
      return <Film className="w-5 h-5 text-indigo-500" />;
    }
    if (item.evidence_type.includes('AI_')) {
      return <Cpu className="w-5 h-5 text-cyan-500" />;
    }
    if (item.evidence_type.includes('DOC') || item.evidence_type.includes('REPORT') || item.evidence_type.includes('NOTE')) {
      return <FileText className="w-5 h-5 text-amber-500" />;
    }
    if (item.evidence_type.includes('ALERT') || item.evidence_type.includes('NOTIFICATION')) {
      return <AlertCircle className="w-5 h-5 text-rose-500" />;
    }
    return <Camera className="w-5 h-5 text-blue-500" />;
  };

  const getStatusBadge = () => {
    switch (item.status) {
      case 'AVAILABLE':
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-green-100 text-green-800">AVAILABLE</span>;
      case 'FINALIZED':
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-blue-100 text-blue-800 border border-blue-300">FINALIZED</span>;
      case 'ARCHIVED':
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-700">ARCHIVED</span>;
      case 'EXPIRED':
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-amber-100 text-amber-800">EXPIRED</span>;
      case 'INTEGRITY_FAILED':
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-red-100 text-red-800 animate-pulse">INTEGRITY FAILED</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-600">{item.status}</span>;
    }
  };

  const getClassificationBadge = () => {
    switch (item.classification) {
      case 'HIGHLY_RESTRICTED':
        return <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-900 text-red-100">HIGHLY RESTRICTED</span>;
      case 'SENSITIVE':
        return <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-purple-100 text-purple-800">SENSITIVE</span>;
      case 'RESTRICTED':
        return <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-orange-100 text-orange-800">RESTRICTED</span>;
      default:
        return <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-700">INTERNAL</span>;
    }
  };

  const formatFileSize = (bytes?: number | null) => {
    if (!bytes) return 'No file';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between overflow-hidden">
      <div className="p-4">
        {/* Top Header */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-gray-50 rounded-lg border border-gray-100">
              {getTypeIcon()}
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-mono text-sm font-bold text-gray-900 hover:text-blue-600 cursor-pointer" onClick={() => onSelect(item)}>
                  {item.evidence_id}
                </span>
                {item.version_number > 1 && (
                  <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                    v{item.version_number}
                  </span>
                )}
              </div>
              <div className="text-xs text-gray-500 font-medium">{item.evidence_type.replace(/_/g, ' ')}</div>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            {getStatusBadge()}
            {getClassificationBadge()}
          </div>
        </div>

        {/* Description / Summary */}
        <p className="text-xs text-gray-600 line-clamp-2 mt-2 mb-3 min-h-[32px]">
          {item.description || item.file_name || 'No description recorded'}
        </p>

        {/* Metadata Details */}
        <div className="grid grid-cols-2 gap-2 text-xs bg-gray-50 p-2.5 rounded border border-gray-100 mb-3">
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Case</span>
            <span className="font-semibold text-gray-800">{item.case_number || (item.case_id ? `Case #${item.case_id}` : 'Unlinked')}</span>
          </div>
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Camera</span>
            <span className="font-medium text-gray-800">{item.camera_id ? `CAM-${item.camera_id}` : 'N/A'}</span>
          </div>
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Size</span>
            <span className="text-gray-700">{formatFileSize(item.file_size)}</span>
          </div>
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Integrity</span>
            <span className="flex items-center gap-1 text-gray-700">
              {item.integrity_status === 'VERIFIED' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
              {item.integrity_status === 'FAILED' && <XCircle className="w-3.5 h-3.5 text-rose-600" />}
              {item.integrity_status !== 'VERIFIED' && item.integrity_status !== 'FAILED' && <Clock className="w-3.5 h-3.5 text-gray-400" />}
              {item.integrity_status}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between text-[11px] text-gray-400">
          <span>Captured: {item.captured_at ? new Date(item.captured_at).toLocaleDateString() : 'N/A'}</span>
          <span>Created: {new Date(item.created_at).toLocaleDateString()}</span>
        </div>
      </div>

      {/* Action Footer */}
      <div className="border-t border-gray-100 bg-gray-50/50 px-4 py-2.5 flex items-center justify-between">
        <button
          onClick={() => onSelect(item)}
          className="text-xs font-semibold text-blue-600 hover:text-blue-800"
        >
          View Evidence &rarr;
        </button>
        {onViewTimeline && (
          <button
            onClick={() => onViewTimeline(item)}
            className="text-xs font-medium text-gray-600 hover:text-gray-800"
          >
            Timeline
          </button>
        )}
      </div>
    </div>
  );
};
