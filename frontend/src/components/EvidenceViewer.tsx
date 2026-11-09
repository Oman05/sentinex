import React, { useState, useEffect } from 'react';
import { Camera, User, AlertTriangle, ShieldCheck, Download, Lock, CheckCircle2, XCircle } from 'lucide-react';
import type { ReviewEventDetail } from '../types/review';
import type { EvidenceItem } from '../types/evidence';
import { StatusBadge } from './StatusBadge';
import { downloadEvidenceContent } from '../services/evidenceApi';

interface EvidenceViewerProps {
  event?: ReviewEventDetail;
  evidence?: EvidenceItem;
  item?: EvidenceItem;
}

export const EvidenceViewer: React.FC<EvidenceViewerProps> = ({ event, evidence, item }) => {
  const currentEvidence = evidence || item;

  // Module 10 standalone secure image viewer
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reasonModalOpen, setReasonModalOpen] = useState(false);
  const [downloadReason, setDownloadReason] = useState('');

  useEffect(() => {
    if (!currentEvidence) return;

    // Load preview if it's an image or crop
    const isImage = currentEvidence.evidence_type.includes('IMAGE') ||
                    currentEvidence.evidence_type.includes('CROP') ||
                    currentEvidence.evidence_type.includes('FRAME') ||
                    currentEvidence.evidence_type.includes('SNAPSHOT');

    if (isImage) {
      setLoading(true);
      setError(null);
      downloadEvidenceContent(currentEvidence.evidence_id, 'Authorized preview in evidence viewer')
        .then((blob) => {
          const url = URL.createObjectURL(blob);
          setImageUrl(url);
        })
        .catch((err) => {
          setError(err.response?.data?.detail || 'Authenticated preview unavailable');
        })
        .finally(() => setLoading(false));
    }

    return () => {
      if (imageUrl) URL.revokeObjectURL(imageUrl);
    };
  }, [currentEvidence?.evidence_id]);

  // If Module 8 event is provided (backwards compatibility)
  if (event && !currentEvidence) {
    return (
      <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-3 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-amber-600" />
          <span className="text-sm font-bold text-amber-900">
            POSSIBLE MATCH — HUMAN REVIEW REQUIRED. Do not confirm identity based solely on this AI-generated match.
          </span>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-gray-200">
          <div className="p-4 flex flex-col h-full">
            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <Camera className="w-5 h-5 text-gray-500" />
              CCTV Observation
            </h3>
            
            <div className="bg-gray-900 rounded-lg aspect-video flex items-center justify-center relative mb-4">
              <div className="absolute top-2 left-2 bg-black bg-opacity-70 text-white text-xs px-2 py-1 rounded font-mono">
                CAM-{event.camera_id || 'UNK'} • {new Date(event.created_at).toLocaleTimeString()}
              </div>
              {event.track_id && (
                <div className="absolute top-2 right-2 bg-blue-600 text-white text-xs px-2 py-1 rounded font-mono">
                  TRK: {event.track_id.substring(0, 8)}
                </div>
              )}
              <div className="text-gray-500 flex flex-col items-center">
                <Camera className="w-12 h-12 mb-2 opacity-50" />
                <span>CCTV Frame Area</span>
                <span className="text-xs mt-1">Image data retrieved securely</span>
              </div>
            </div>
            
            <div className="bg-gray-50 rounded p-3 text-sm grid grid-cols-2 gap-2 mt-auto">
              <div>
                <span className="text-gray-500 block text-xs">Location</span>
                <span className="font-medium text-gray-900">{event.camera_location || 'Unknown'}</span>
              </div>
              <div>
                <span className="text-gray-500 block text-xs">Time</span>
                <span className="font-medium text-gray-900">{new Date(event.created_at).toLocaleString()}</span>
              </div>
              <div>
                <span className="text-gray-500 block text-xs">Face Quality</span>
                <span className="font-medium text-gray-900">{event.face_quality_label || 'N/A'}</span>
              </div>
              <div>
                <span className="text-gray-500 block text-xs">Detection Score</span>
                <span className="font-medium text-gray-900">{event.detection_quality_score?.toFixed(2) || 'N/A'}</span>
              </div>
            </div>
          </div>

          <div className="p-4 flex flex-col h-full">
            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <User className="w-5 h-5 text-gray-500" />
              Enrolled Reference ({event.case_number})
            </h3>
            
            <div className="bg-gray-100 rounded-lg aspect-video flex items-center justify-center relative mb-4 border border-gray-200">
              <div className="text-gray-400 flex flex-col items-center">
                <User className="w-12 h-12 mb-2 opacity-50" />
                <span>Reference Image</span>
              </div>
            </div>
            
            <div className="bg-gray-50 rounded p-3 text-sm grid grid-cols-2 gap-2 mt-auto">
              <div>
                <span className="text-gray-500 block text-xs">Subject Name</span>
                <span className="font-medium text-gray-900">{(event as any).case_title || event.case_number || 'N/A'}</span>
              </div>
              <div>
                <span className="text-gray-500 block text-xs">Category</span>
                <span className="font-medium text-gray-900">{event.category}</span>
              </div>
              <div>
                <span className="text-gray-500 block text-xs">Case Number</span>
                <span className="font-medium text-gray-900">{event.case_number}</span>
              </div>
              <div>
                <span className="text-gray-500 block text-xs">Review Status</span>
                <StatusBadge status={event.status} />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Module 10 Secure Evidence Viewer UI (Section 14)
  if (!currentEvidence) {
    return <div className="p-6 text-center text-gray-400">No evidence selected.</div>;
  }

  const handleDownload = async () => {
    if (downloadReason.trim().length < 5) return;
    try {
      const blob = await downloadEvidenceContent(currentEvidence.evidence_id, downloadReason);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = currentEvidence.file_name || `${currentEvidence.evidence_id}.bin`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setReasonModalOpen(false);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Download failed');
    }
  };

  return (
    <div className="bg-white rounded-xl shadow border border-gray-200 overflow-hidden flex flex-col">
      {/* Header */}
      <div className="bg-gray-900 text-white px-5 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-blue-400" />
          <span className="font-bold text-sm tracking-wide">SECURE EVIDENCE VIEWER</span>
          <span className="bg-blue-950 text-blue-300 text-[10px] px-2 py-0.5 rounded font-bold border border-blue-800">
            {currentEvidence.classification}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setReasonModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1 bg-gray-800 hover:bg-gray-700 text-white text-xs font-semibold rounded transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Authorized Export
          </button>
        </div>
      </div>

      {/* Main View Area */}
      <div className="p-6 bg-gray-50 flex flex-col items-center justify-center min-h-[340px] relative select-none">
        {loading && (
          <div className="flex flex-col items-center gap-2 text-gray-500">
            <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
            <span className="text-xs">Verifying credentials and loading secure artifact...</span>
          </div>
        )}

        {!loading && imageUrl && (
          <div className="relative max-h-[460px] max-w-full rounded-lg overflow-hidden border border-gray-300 shadow bg-black">
            <img
              src={imageUrl}
              alt="Authorized Evidence"
              className="max-h-[460px] object-contain"
              onContextMenu={(e) => e.preventDefault()}
            />
            {/* Watermark */}
            <div className="absolute bottom-2 left-2 bg-black/70 text-white text-[10px] font-mono px-2 py-1 rounded pointer-events-none">
              {currentEvidence.evidence_id} • CAM-{currentEvidence.camera_id || 'UNK'} • LAW ENFORCEMENT ONLY
            </div>
          </div>
        )}

        {!loading && !imageUrl && (
          <div className="p-8 text-center text-gray-400 max-w-sm">
            <Lock className="w-12 h-12 mx-auto mb-2 text-gray-300" />
            <div className="text-sm font-semibold text-gray-700">Authenticated File Asset</div>
            <p className="text-xs text-gray-500 mt-1">
              {currentEvidence.file_name || 'Evidence metadata registered'}.
              {error ? ` (${error})` : ' Preview rendered safely via authenticated backend stream.'}
            </p>
          </div>
        )}
      </div>

      {/* Section 14 Metadata Panel */}
      <div className="p-4 bg-white border-t border-gray-200 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
        <div>
          <span className="text-gray-500 block uppercase font-medium text-[10px]">Evidence ID</span>
          <span className="font-mono font-bold text-gray-900">{currentEvidence.evidence_id}</span>
        </div>
        <div>
          <span className="text-gray-500 block uppercase font-medium text-[10px]">Camera</span>
          <span className="font-semibold text-gray-900">{currentEvidence.camera_id ? `CCTV-${currentEvidence.camera_id}` : 'N/A'}</span>
        </div>
        <div>
          <span className="text-gray-500 block uppercase font-medium text-[10px]">Captured</span>
          <span className="font-medium text-gray-900">
            {currentEvidence.captured_at ? new Date(currentEvidence.captured_at).toLocaleTimeString() : 'N/A'}
          </span>
        </div>
        <div>
          <span className="text-gray-500 block uppercase font-medium text-[10px]">Integrity Hash</span>
          <span className="inline-flex items-center gap-1 font-semibold text-gray-900">
            {currentEvidence.integrity_status === 'VERIFIED' && (
              <span className="text-emerald-700 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> VERIFIED
              </span>
            )}
            {currentEvidence.integrity_status === 'FAILED' && (
              <span className="text-rose-700 flex items-center gap-1">
                <XCircle className="w-3.5 h-3.5 text-rose-600" /> FAILED
              </span>
            )}
            {currentEvidence.integrity_status !== 'VERIFIED' && currentEvidence.integrity_status !== 'FAILED' && (
              <span className="text-gray-600">{currentEvidence.integrity_status}</span>
            )}
          </span>
        </div>
      </div>

      {/* Export Reason Modal */}
      {reasonModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-2xl border border-gray-200">
            <h3 className="text-sm font-bold text-gray-900 mb-2">Mandatory Evidence Download Justification</h3>
            <p className="text-xs text-gray-600 mb-4">
              All evidence extraction is bound by policy. State the official purpose to record in the permanent audit trail.
            </p>
            <textarea
              value={downloadReason}
              onChange={(e) => setDownloadReason(e.target.value)}
              placeholder="e.g. Case WP-2026-0012 evidence docket compilation for court filing..."
              className="w-full border border-gray-300 rounded-lg p-2.5 text-xs text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 h-24 mb-4"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setReasonModalOpen(false)}
                className="px-3 py-1.5 text-xs text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleDownload}
                disabled={downloadReason.trim().length < 5}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white text-xs font-semibold rounded-lg"
              >
                Confirm Download
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
