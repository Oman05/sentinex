import React, { useState } from 'react';
import { CheckCircle2, XCircle, Clock, AlertTriangle, RefreshCw, Copy, Check } from 'lucide-react';
import type { IntegrityStatusType } from '../types/evidence';
import { verifyEvidenceIntegrity } from '../services/evidenceApi';

interface IntegrityStatusProps {
  evidenceId: string;
  status: IntegrityStatusType;
  fileHash?: string | null;
  hashAlgorithm?: string;
  lastCheckedAt?: string | null;
  onVerified?: (status: IntegrityStatusType) => void;
}

export const IntegrityStatus: React.FC<IntegrityStatusProps> = ({
  evidenceId,
  status: initialStatus,
  fileHash,
  hashAlgorithm = 'SHA-256',
  lastCheckedAt,
  onVerified,
}) => {
  const [status, setStatus] = useState<IntegrityStatusType>(initialStatus);
  const [verifying, setVerifying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const handleVerify = async () => {
    try {
      setVerifying(true);
      setMessage(null);
      const res = await verifyEvidenceIntegrity(evidenceId);
      setStatus(res.integrity_status);
      setMessage(res.message);
      if (onVerified) onVerified(res.integrity_status);
    } catch (err: any) {
      setMessage(err.response?.data?.detail || 'Integrity check failed to execute');
    } finally {
      setVerifying(false);
    }
  };

  const handleCopyHash = () => {
    if (fileHash) {
      navigator.clipboard.writeText(fileHash);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const getStatusBadge = () => {
    switch (status) {
      case 'VERIFIED':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            INTEGRITY VERIFIED
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300 animate-pulse">
            <XCircle className="w-4 h-4 text-rose-600" />
            INTEGRITY CHECK FAILED
          </span>
        );
      case 'PENDING':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            <Clock className="w-4 h-4 text-amber-600" />
            VERIFICATION PENDING
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-800 border border-gray-300">
            <AlertTriangle className="w-4 h-4 text-gray-500" />
            NOT VERIFIED
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="flex items-center justify-between gap-4 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">Hash Baseline:</span>
          {getStatusBadge()}
        </div>
        <button
          onClick={handleVerify}
          disabled={verifying}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-800 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${verifying ? 'animate-spin' : ''}`} />
          {verifying ? 'Checking...' : 'Re-verify Hash'}
        </button>
      </div>

      {fileHash ? (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>Algorithm: <strong className="text-gray-700">{hashAlgorithm}</strong></span>
            {lastCheckedAt && (
              <span>Last checked: {new Date(lastCheckedAt).toLocaleTimeString()}</span>
            )}
          </div>
          <div className="flex items-center gap-2 bg-gray-50 rounded p-2 border border-gray-200 font-mono text-xs text-gray-700 break-all select-all">
            <span className="flex-1 truncate">{fileHash}</span>
            <button
              onClick={handleCopyHash}
              className="text-gray-400 hover:text-gray-600 p-1 rounded hover:bg-gray-200 flex-shrink-0"
              title="Copy hash"
            >
              {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
        </div>
      ) : (
        <div className="text-xs text-gray-500 italic">No cryptographic hash baseline stored for this record.</div>
      )}

      {status === 'FAILED' && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-xs text-red-800 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <strong>CRITICAL: HASH MISMATCH DETECTED.</strong>
            <p className="mt-0.5">
              The file content does not match the baseline hash recorded upon upload.
              Do NOT silently overwrite or delete the evidence. Escalate to the department auditor.
            </p>
          </div>
        </div>
      )}

      {message && status !== 'FAILED' && (
        <div className="mt-2 text-xs text-gray-600 italic">
          {message}
        </div>
      )}
    </div>
  );
};
