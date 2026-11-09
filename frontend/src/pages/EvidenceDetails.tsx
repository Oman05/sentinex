import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  FolderLock,
  ArrowLeft,
  ShieldCheck,
  Lock,
  GitBranch,
  Archive,
  Download,
  Clock,
  Eye,
  AlertTriangle,
  History,
  FileCheck2,
} from 'lucide-react';
import type {
  EvidenceItem,
  ChainOfCustodyResponse,
  EvidenceProvenanceResponse,
  AccessLogItem,
} from '../types/evidence';
import {
  getEvidence,
  getChainOfCustody,
  getEvidenceProvenance,
  getEvidenceAccessLogs,
  finalizeEvidence,
  archiveEvidence,
  createEvidenceVersion,
  exportEvidence,
} from '../services/evidenceApi';
import { EvidenceViewer } from '../components/EvidenceViewer';
import { VideoEvidenceViewer } from '../components/VideoEvidenceViewer';
import { IntegrityStatus } from '../components/IntegrityStatus';
import { ChainOfCustody } from '../components/ChainOfCustody';

export default function EvidenceDetails() {
  const { evidenceId } = useParams<{ evidenceId: string }>();
  const navigate = useNavigate();

  const [evidence, setEvidence] = useState<EvidenceItem | null>(null);
  const [custody, setCustody] = useState<ChainOfCustodyResponse | null>(null);
  const [provenance, setProvenance] = useState<EvidenceProvenanceResponse | null>(null);
  const [accessLogs, setAccessLogs] = useState<AccessLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'viewer' | 'provenance' | 'custody' | 'access'>('viewer');

  // Modals
  const [finalizeModalOpen, setFinalizeModalOpen] = useState(false);
  const [finalizeReason, setFinalizeReason] = useState('');
  const [finalizeNotes, setFinalizeNotes] = useState('');

  const [archiveModalOpen, setArchiveModalOpen] = useState(false);
  const [archiveReason, setArchiveReason] = useState('');

  const [versionModalOpen, setVersionModalOpen] = useState(false);
  const [versionNotes, setVersionNotes] = useState('');
  const [versionFile, setVersionFile] = useState<File | null>(null);

  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportType, setExportType] = useState('DOWNLOAD');
  const [exportReason, setExportReason] = useState('');
  const [exportDestination, setExportDestination] = useState('');

  const loadData = async () => {
    if (!evidenceId) return;
    try {
      setLoading(true);
      setError(null);
      const item = await getEvidence(evidenceId);
      setEvidence(item);

      // Concurrently load supplementary audit info
      const [custodyRes, provRes, logsRes] = await Promise.all([
        getChainOfCustody(evidenceId).catch(() => null),
        getEvidenceProvenance(evidenceId).catch(() => null),
        getEvidenceAccessLogs(evidenceId).catch(() => []),
      ]);
      setCustody(custodyRes);
      setProvenance(provRes);
      setAccessLogs(logsRes);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load evidence details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [evidenceId]);

  const handleFinalize = async () => {
    if (!evidenceId || finalizeReason.trim().length < 3) return;
    try {
      const updated = await finalizeEvidence(evidenceId, finalizeReason, finalizeNotes);
      setEvidence(updated);
      setFinalizeModalOpen(false);
      loadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to finalize evidence');
    }
  };

  const handleArchive = async () => {
    if (!evidenceId || archiveReason.trim().length < 5) return;
    try {
      const updated = await archiveEvidence(evidenceId, archiveReason);
      setEvidence(updated);
      setArchiveModalOpen(false);
      loadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to archive evidence');
    }
  };

  const handleCreateVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!evidenceId) return;
    try {
      const data = new FormData();
      if (versionNotes) data.append('version_notes', versionNotes);
      if (versionFile) data.append('file', versionFile);

      const newVer = await createEvidenceVersion(evidenceId, data);
      setVersionModalOpen(false);
      navigate(`/evidence/${newVer.evidence_id}`);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create new version');
    }
  };

  const handleExport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!evidenceId || exportReason.trim().length < 5) return;
    try {
      await exportEvidence(evidenceId, {
        export_type: exportType,
        reason: exportReason,
        destination: exportDestination || undefined,
      });
      setExportModalOpen(false);
      loadData();
      alert(`Export recorded as ${exportType}. Transaction logged in audit trail.`);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to record export event');
    }
  };

  if (loading) {
    return (
      <div className="p-16 text-center text-gray-400">
        <FolderLock className="w-10 h-10 mx-auto mb-2 text-blue-500 animate-spin" />
        <span>Authenticating and retrieving secure evidence record...</span>
      </div>
    );
  }

  if (error || !evidence) {
    return (
      <div className="bg-white rounded-xl p-8 border border-red-200 text-center max-w-lg mx-auto">
        <AlertTriangle className="w-12 h-12 text-rose-500 mx-auto mb-3" />
        <h2 className="text-lg font-bold text-gray-900">Access Denied or Not Found</h2>
        <p className="text-xs text-gray-500 mt-1 mb-4">{error || 'Unable to retrieve evidence item.'}</p>
        <button
          onClick={() => navigate('/evidence')}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-xs font-semibold"
        >
          &larr; Back to Evidence Dashboard
        </button>
      </div>
    );
  }

  const isVideo = evidence.evidence_type.includes('CLIP') || evidence.evidence_type.includes('VIDEO');

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/evidence')}
            className="p-2 bg-white border border-gray-200 rounded-lg text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold font-mono text-gray-900">{evidence.evidence_id}</h1>
              {evidence.version_number > 1 && (
                <span className="px-2 py-0.5 rounded text-xs font-bold bg-indigo-100 text-indigo-800">
                  Version {evidence.version_number}
                </span>
              )}
              {evidence.status === 'FINALIZED' && (
                <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-blue-100 text-blue-800 border border-blue-300 flex items-center gap-1">
                  <Lock className="w-3 h-3" /> FINALIZED (IMMUTABLE)
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              Type: <strong className="text-gray-700">{evidence.evidence_type.replace(/_/g, ' ')}</strong> • Case:{' '}
              <strong className="text-gray-700">{evidence.case_number || 'Unlinked'}</strong>
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          {evidence.status !== 'FINALIZED' && (
            <button
              onClick={() => setFinalizeModalOpen(true)}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 shadow-sm"
            >
              <FileCheck2 className="w-3.5 h-3.5" />
              Finalize Evidence
            </button>
          )}

          <button
            onClick={() => setVersionModalOpen(true)}
            className="px-3 py-1.5 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-xs font-semibold rounded-lg flex items-center gap-1.5 shadow-sm"
          >
            <GitBranch className="w-3.5 h-3.5 text-indigo-500" />
            Create Derived Version
          </button>

          {evidence.status !== 'ARCHIVED' && (
            <button
              onClick={() => setArchiveModalOpen(true)}
              className="px-3 py-1.5 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-xs font-semibold rounded-lg flex items-center gap-1.5 shadow-sm"
            >
              <Archive className="w-3.5 h-3.5 text-gray-500" />
              Archive
            </button>
          )}

          <button
            onClick={() => setExportModalOpen(true)}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 shadow-sm"
          >
            <Download className="w-3.5 h-3.5 text-amber-400" />
            Authorized Export
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 flex gap-4">
        {[
          { key: 'viewer', label: 'Evidence Asset Viewer', icon: Eye },
          { key: 'provenance', label: 'Event Provenance Chain', icon: GitBranch },
          { key: 'custody', label: 'Chain of Custody', icon: ShieldCheck },
          { key: 'access', label: 'Access Audit Ledger', icon: History },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            className={`pb-3 text-xs font-semibold flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === tab.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Viewer & Integrity */}
      {activeTab === 'viewer' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            {isVideo ? (
              <VideoEvidenceViewer item={evidence} />
            ) : (
              <EvidenceViewer evidence={evidence} />
            )}
          </div>

          <div className="space-y-6">
            {/* Integrity Status Verification Component */}
            <IntegrityStatus
              evidenceId={evidence.evidence_id}
              status={evidence.integrity_status}
              fileHash={evidence.file_hash}
              hashAlgorithm={evidence.hash_algorithm}
              lastCheckedAt={evidence.last_integrity_check_at}
              onVerified={(newStatus) => setEvidence({ ...evidence, integrity_status: newStatus })}
            />

            {/* Retention & Lifecycle Info */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm text-xs space-y-3">
              <h3 className="font-bold text-gray-900 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-gray-500" />
                Retention &amp; Lifecycle Policy
              </h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-500">Status:</span>
                  <span className="font-bold text-gray-900">{evidence.status}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Classification:</span>
                  <span className="font-semibold text-gray-900">{evidence.classification}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Storage Backend:</span>
                  <span className="font-mono text-gray-900">{evidence.storage_backend}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Retention Expiry:</span>
                  <span className="text-gray-700">
                    {evidence.retention_expires_at
                      ? new Date(evidence.retention_expires_at).toLocaleDateString()
                      : 'Indefinite / Under Policy Review'}
                  </span>
                </div>
              </div>

              {evidence.version_notes && (
                <div className="pt-2 border-t border-gray-100">
                  <span className="text-gray-500 block text-[10px] uppercase font-semibold">Version Notes</span>
                  <p className="text-gray-700 italic mt-0.5">{evidence.version_notes}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Provenance Chain (Section 5 & 40) */}
      {activeTab === 'provenance' && provenance && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-6">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-xs text-blue-900 leading-relaxed">
            <h4 className="font-bold mb-1 flex items-center gap-1.5">
              <GitBranch className="w-4 h-4 text-blue-600" />
              Section 5 Provenance Verification
            </h4>
            {provenance.explanation}
          </div>

          <div className="space-y-4">
            <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide">
              Event Generation Pipeline (CCTV &rarr; Match &rarr; Review &rarr; Alert &rarr; Evidence)
            </h4>
            <div className="relative border-l-2 border-blue-300 ml-4 space-y-6">
              {provenance.chain_of_events.map((step, idx) => (
                <div key={idx} className="relative pl-6">
                  <div className="absolute -left-[9px] top-1.5 w-4 h-4 bg-blue-600 rounded-full border-2 border-white shadow-sm"></div>
                  <div className="bg-gray-50 rounded-lg p-3.5 border border-gray-200">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs font-bold text-blue-700">{step.stage}</span>
                      <span className="font-mono text-xs text-gray-500">{step.identifier}</span>
                    </div>
                    <div className="text-xs font-semibold text-gray-900">{step.label}</div>
                    {step.timestamp && (
                      <div className="text-[11px] text-gray-500 mt-1">
                        Recorded: {new Date(step.timestamp).toLocaleString()}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Chain of Custody */}
      {activeTab === 'custody' && custody && (
        <ChainOfCustody
          evidenceId={evidence.evidence_id}
          evidenceType={evidence.evidence_type}
          caseNumber={evidence.case_number}
          events={custody.chain}
          disclaimer={custody.disclaimer}
        />
      )}

      {/* Tab 4: Access Audit Ledger */}
      {activeTab === 'access' && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="p-4 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
            <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wide flex items-center gap-2">
              <History className="w-4 h-4 text-gray-600" />
              Evidence Access &amp; Inspection History
            </h3>
            <span className="text-xs text-gray-500">Every view and download is recorded</span>
          </div>

          {accessLogs.length === 0 ? (
            <div className="p-8 text-center text-xs text-gray-500">No access records logged yet.</div>
          ) : (
            <div className="divide-y divide-gray-100 text-xs">
              {accessLogs.map((log) => (
                <div key={log.id} className="p-4 flex items-start justify-between gap-4 hover:bg-gray-50/50">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-gray-900">{log.action}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          log.access_granted ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {log.access_granted ? 'GRANTED' : 'DENIED'}
                      </span>
                    </div>
                    <div className="text-gray-600 mt-1">
                      User: <strong>{log.actor_username || 'SYSTEM'}</strong>
                      {log.reason && <span className="italic ml-2">Reason: "{log.reason}"</span>}
                    </div>
                    {log.denial_reason && (
                      <div className="text-rose-600 mt-0.5 font-medium">Denied: {log.denial_reason}</div>
                    )}
                  </div>
                  <div className="text-right text-gray-400 font-mono text-[11px]">
                    <div>{new Date(log.timestamp).toLocaleDateString()}</div>
                    <div>{new Date(log.timestamp).toLocaleTimeString()}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Modal: Finalize Evidence */}
      {finalizeModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-md w-full shadow-2xl border border-gray-200">
            <h3 className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-2">
              <Lock className="w-4 h-4 text-blue-600" />
              Finalize Evidence Item
            </h3>
            <p className="text-xs text-gray-600 mb-4">
              Finalizing locks this evidence item as immutable. Subsequent edits are blocked; new versions must be derived.
            </p>
            <div className="space-y-3 text-xs mb-4">
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Finalization Justification *</label>
                <textarea
                  value={finalizeReason}
                  onChange={(e) => setFinalizeReason(e.target.value)}
                  placeholder="e.g. Approved match confirmed by supervising investigator..."
                  className="w-full border rounded p-2 text-xs h-20"
                />
              </div>
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Docket Notes (optional)</label>
                <input
                  type="text"
                  value={finalizeNotes}
                  onChange={(e) => setFinalizeNotes(e.target.value)}
                  placeholder="e.g. Transferred to evidence locker #4"
                  className="w-full border rounded p-2 text-xs"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setFinalizeModalOpen(false)}
                className="px-3 py-1.5 text-xs text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleFinalize}
                disabled={finalizeReason.trim().length < 3}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-semibold rounded text-xs"
              >
                Confirm Finalization
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Archive Evidence */}
      {archiveModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-md w-full shadow-2xl border border-gray-200">
            <h3 className="text-sm font-bold text-gray-900 mb-2">Archive Evidence Record</h3>
            <p className="text-xs text-gray-600 mb-4">
              Archived evidence remains discoverable to authorized personnel. Original files and audit history are preserved.
            </p>
            <textarea
              value={archiveReason}
              onChange={(e) => setArchiveReason(e.target.value)}
              placeholder="State reason for archiving (e.g. Case WP-2026-0012 resolved and closed)..."
              className="w-full border rounded p-2 text-xs h-20 mb-4"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setArchiveModalOpen(false)}
                className="px-3 py-1.5 text-xs text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleArchive}
                disabled={archiveReason.trim().length < 5}
                className="px-4 py-1.5 bg-gray-800 hover:bg-gray-900 disabled:opacity-40 text-white font-semibold rounded text-xs"
              >
                Confirm Archive
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Create Derived Version */}
      {versionModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-md w-full shadow-2xl border border-gray-200">
            <h3 className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-indigo-600" />
              Create Derived Evidence Version
            </h3>
            <p className="text-xs text-gray-600 mb-4">
              Original record remains completely intact. A new version record is created and linked in the provenance chain.
            </p>
            <form onSubmit={handleCreateVersion} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Version Notes / Revision Reason *</label>
                <textarea
                  value={versionNotes}
                  onChange={(e) => setVersionNotes(e.target.value)}
                  placeholder="e.g. Enhanced resolution crop of suspect face from original frame..."
                  className="w-full border rounded p-2 text-xs h-20"
                  required
                />
              </div>
              <div>
                <label className="block font-semibold text-gray-700 mb-1">New File Asset (optional)</label>
                <input
                  type="file"
                  onChange={(e) => setVersionFile(e.target.files?.[0] || null)}
                  className="w-full border rounded p-1.5 text-xs bg-gray-50"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setVersionModalOpen(false)}
                  className="px-3 py-1.5 text-xs text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded text-xs"
                >
                  Create Version
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Authorized Export */}
      {exportModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-md w-full shadow-2xl border border-gray-200">
            <h3 className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-2">
              <Download className="w-4 h-4 text-amber-500" />
              Authorized Evidence Export
            </h3>
            <p className="text-xs text-gray-600 mb-4">
              Exports create an official immutable audit record with hash snapshots.
            </p>
            <form onSubmit={handleExport} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Export Type *</label>
                <select
                  value={exportType}
                  onChange={(e) => setExportType(e.target.value)}
                  className="w-full border rounded p-2 text-xs"
                >
                  <option value="DOWNLOAD">DOWNLOAD (Digital File Extraction)</option>
                  <option value="REPORT">REPORT (Investigation Docket Package)</option>
                  <option value="SHARE">SHARE (Inter-departmental Transfer)</option>
                  <option value="PRINT">PRINT (Hardcopy Evidence Sheet)</option>
                </select>
              </div>
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Mandatory Export Justification *</label>
                <textarea
                  value={exportReason}
                  onChange={(e) => setExportReason(e.target.value)}
                  placeholder="Official investigation purpose or judicial subpoena..."
                  className="w-full border rounded p-2 text-xs h-20"
                  required
                />
              </div>
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Recipient / Destination Reference</label>
                <input
                  type="text"
                  value={exportDestination}
                  onChange={(e) => setExportDestination(e.target.value)}
                  placeholder="e.g. County Prosecutor Office / Dept #204"
                  className="w-full border rounded p-2 text-xs"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setExportModalOpen(false)}
                  className="px-3 py-1.5 text-xs text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={exportReason.trim().length < 5}
                  className="px-4 py-1.5 bg-slate-900 hover:bg-black disabled:opacity-40 text-white font-semibold rounded text-xs"
                >
                  Execute Export
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
