import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FolderLock,
  Camera,
  Film,
  FileText,
  ShieldAlert,
  Search,
  Plus,
  RefreshCw,
  HardDrive,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import type { EvidenceItem, EvidenceStats } from '../types/evidence';
import { getEvidenceStats, listEvidence, createEvidence } from '../services/evidenceApi';
import { EvidenceCard } from '../components/EvidenceCard';

export default function EvidenceDashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<EvidenceStats | null>(null);
  const [items, setItems] = useState<EvidenceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [classificationFilter, setClassificationFilter] = useState('');
  const [page, setPage] = useState(1);

  // New Evidence Modal State
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    evidence_type: 'CCTV_FRAME',
    classification: 'RESTRICTED',
    case_id: '',
    camera_id: '',
    description: '',
    tags: '',
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [statsRes, listRes] = await Promise.all([
        getEvidenceStats(),
        listEvidence({
          q: searchQuery || undefined,
          evidence_type: typeFilter || undefined,
          status: statusFilter || undefined,
          classification: classificationFilter || undefined,
          page,
          page_size: 12,
        }),
      ]);
      setStats(statsRes);
      setItems(listRes.items);
      setTotal(listRes.total);
    } catch (err) {
      console.error('Failed to load evidence dashboard', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [searchQuery, typeFilter, statusFilter, classificationFilter, page]);

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploadLoading(true);
    setUploadError(null);

    try {
      const data = new FormData();
      data.append('evidence_type', formData.evidence_type);
      data.append('classification', formData.classification);
      if (formData.case_id) data.append('case_id', formData.case_id);
      if (formData.camera_id) data.append('camera_id', formData.camera_id);
      if (formData.description) data.append('description', formData.description);
      if (formData.tags) data.append('tags', formData.tags);
      if (selectedFile) data.append('file', selectedFile);

      await createEvidence(data);
      setUploadModalOpen(false);
      setSelectedFile(null);
      setFormData({
        evidence_type: 'CCTV_FRAME',
        classification: 'RESTRICTED',
        case_id: '',
        camera_id: '',
        description: '',
        tags: '',
      });
      fetchData();
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'Failed to upload evidence');
    } finally {
      setUploadLoading(false);
    }
  };

  const formatBytes = (bytes?: number) => {
    if (!bytes) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-2.5">
            <FolderLock className="w-7 h-7 text-blue-600" />
            EVIDENCE MANAGEMENT SYSTEM
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Module 10 • Cryptographically verified evidence repository, chain of custody &amp; full audit trail
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setUploadModalOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            Ingest Evidence
          </button>
          <button
            onClick={() => navigate('/audit')}
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            System Audit Trail
          </button>
        </div>
      </div>

      {/* KPI Stats Bar (Section 33) */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm flex items-center gap-3.5">
          <div className="p-3 bg-blue-50 text-blue-600 rounded-lg">
            <FolderLock className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-black text-gray-900">{stats?.total_evidence ?? 0}</div>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Total Evidence</div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm flex items-center gap-3.5">
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-lg">
            <Camera className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-black text-gray-900">
              {(stats?.by_type?.['CCTV_FRAME'] || 0) +
                (stats?.by_type?.['FACE_CROP'] || 0) +
                (stats?.by_type?.['REFERENCE_IMAGE'] || 0) +
                (stats?.by_type?.['EVIDENCE_SNAPSHOT'] || 0)}
            </div>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Images &amp; Frames</div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm flex items-center gap-3.5">
          <div className="p-3 bg-purple-50 text-purple-600 rounded-lg">
            <Film className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-black text-gray-900">
              {(stats?.by_type?.['CCTV_CLIP'] || 0) + (stats?.by_type?.['INVESTIGATION_CLIP'] || 0)}
            </div>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Video Clips</div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm flex items-center gap-3.5">
          <div className="p-3 bg-amber-50 text-amber-600 rounded-lg">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-black text-gray-900">
              {(stats?.by_type?.['CASE_DOCUMENT'] || 0) +
                (stats?.by_type?.['AUTHORIZED_REPORT'] || 0) +
                (stats?.by_type?.['INVESTIGATION_NOTE'] || 0)}
            </div>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Documents</div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm flex items-center gap-3.5">
          <div className="p-3 bg-emerald-50 text-emerald-600 rounded-lg">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-black text-gray-900">{stats?.integrity_verified ?? 0}</div>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Integrity Verified</div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm flex items-center gap-3.5">
          <div className="p-3 bg-slate-50 text-slate-600 rounded-lg">
            <HardDrive className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xl font-bold text-gray-900 truncate">
              {formatBytes(stats?.storage_size_bytes)}
            </div>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Secure Store</div>
          </div>
        </div>
      </div>

      {/* Integrity Alert Banner if Mismatch exists */}
      {stats && stats.integrity_failed > 0 && (
        <div className="bg-rose-50 border-l-4 border-rose-500 p-4 rounded-r-lg shadow-sm flex items-center justify-between">
          <div className="flex items-center gap-3">
            <XCircle className="w-6 h-6 text-rose-600 flex-shrink-0" />
            <div>
              <div className="text-sm font-bold text-rose-900">
                CRITICAL WARNING: {stats.integrity_failed} EVIDENCE ITEM(S) FAILED INTEGRITY VERIFICATION
              </div>
              <div className="text-xs text-rose-700 mt-0.5">
                Hash discrepancies detected against baseline digests. Audit investigation required immediately.
              </div>
            </div>
          </div>
          <button
            onClick={() => setStatusFilter('INTEGRITY_FAILED')}
            className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded shadow-sm"
          >
            Filter Discrepancies
          </button>
        </div>
      )}

      {/* Search & Filter Toolbar */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex flex-col md:flex-row items-center gap-3 justify-between">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by Evidence ID, Case number, tags, or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto flex-wrap">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Types</option>
            <option value="CCTV_FRAME">CCTV Frame</option>
            <option value="FACE_CROP">Face Crop</option>
            <option value="REFERENCE_IMAGE">Reference Image</option>
            <option value="CCTV_CLIP">CCTV Video Clip</option>
            <option value="INVESTIGATION_CLIP">Investigation Clip</option>
            <option value="CASE_DOCUMENT">Case Document</option>
            <option value="AUTHORIZED_REPORT">Authorized Report</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="AVAILABLE">AVAILABLE</option>
            <option value="FINALIZED">FINALIZED</option>
            <option value="ARCHIVED">ARCHIVED</option>
            <option value="EXPIRED">EXPIRED</option>
            <option value="INTEGRITY_FAILED">INTEGRITY_FAILED</option>
          </select>

          <select
            value={classificationFilter}
            onChange={(e) => setClassificationFilter(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Classifications</option>
            <option value="INTERNAL">INTERNAL</option>
            <option value="RESTRICTED">RESTRICTED</option>
            <option value="SENSITIVE">SENSITIVE</option>
            <option value="HIGHLY_RESTRICTED">HIGHLY_RESTRICTED</option>
          </select>

          <button
            onClick={() => {
              setSearchQuery('');
              setTypeFilter('');
              setStatusFilter('');
              setClassificationFilter('');
              setPage(1);
            }}
            className="p-2 text-gray-400 hover:text-gray-600 rounded hover:bg-gray-100"
            title="Reset Filters"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Evidence Content: Grid or Table */}
      {loading ? (
        <div className="p-16 text-center text-gray-400 animate-pulse">
          <FolderLock className="w-10 h-10 mx-auto mb-2 text-blue-500 animate-spin" />
          <span>Querying authorized evidence items...</span>
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <AlertTriangle className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <h3 className="text-base font-bold text-gray-800">No authorized evidence records found</h3>
          <p className="text-xs text-gray-500 max-w-md mx-auto mt-1">
            Either no evidence matches your search criteria, or access is restricted by departmental jurisdiction.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {items.map((item) => (
            <EvidenceCard
              key={item.id}
              item={item}
              onSelect={(selected) => navigate(`/evidence/${selected.evidence_id}`)}
              onViewTimeline={(selected) => navigate(`/evidence/${selected.evidence_id}/timeline`)}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > 12 && (
        <div className="flex items-center justify-between bg-white px-4 py-3 rounded-lg border border-gray-200 text-xs">
          <span className="text-gray-500">
            Showing {(page - 1) * 12 + 1} to {Math.min(page * 12, total)} of {total} items
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 border rounded disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * 12 >= total}
              className="px-3 py-1.5 border rounded disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Ingest Evidence Modal */}
      {uploadModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-lg w-full p-6 shadow-2xl border border-gray-200 max-h-[90vh] overflow-y-auto">
            <h3 className="text-base font-bold text-gray-900 mb-1 flex items-center gap-2">
              <FolderLock className="w-5 h-5 text-blue-600" />
              Ingest Authorized Evidence
            </h3>
            <p className="text-xs text-gray-500 mb-4">
              Files undergo MIME validation, magic-byte inspection, and anti-malware verification before SHA-256 baseline hashing.
            </p>

            {uploadError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-xs text-red-800">
                {uploadError}
              </div>
            )}

            <form onSubmit={handleUploadSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-gray-700 font-semibold mb-1">Evidence Type *</label>
                <select
                  value={formData.evidence_type}
                  onChange={(e) => setFormData({ ...formData, evidence_type: e.target.value })}
                  className="w-full border rounded-lg p-2 text-xs"
                  required
                >
                  <option value="CCTV_FRAME">CCTV Frame</option>
                  <option value="FACE_CROP">Detected Face Crop</option>
                  <option value="REFERENCE_IMAGE">Reference Image</option>
                  <option value="EVIDENCE_SNAPSHOT">Evidence Snapshot</option>
                  <option value="CCTV_CLIP">CCTV Video Clip</option>
                  <option value="INVESTIGATION_CLIP">Investigation Clip</option>
                  <option value="CASE_DOCUMENT">Case Document</option>
                  <option value="AUTHORIZED_REPORT">Authorized Report</option>
                  <option value="INVESTIGATION_NOTE">Investigation Note</option>
                </select>
              </div>

              <div>
                <label className="block text-gray-700 font-semibold mb-1">Classification Level *</label>
                <select
                  value={formData.classification}
                  onChange={(e) => setFormData({ ...formData, classification: e.target.value })}
                  className="w-full border rounded-lg p-2 text-xs"
                  required
                >
                  <option value="INTERNAL">INTERNAL (Internal departmental use)</option>
                  <option value="RESTRICTED">RESTRICTED (Case-assigned officers only)</option>
                  <option value="SENSITIVE">SENSITIVE (Supervisor authorization required)</option>
                  <option value="HIGHLY_RESTRICTED">HIGHLY_RESTRICTED (Admin / Internal Affairs)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 font-semibold mb-1">Case ID (optional)</label>
                  <input
                    type="number"
                    value={formData.case_id}
                    onChange={(e) => setFormData({ ...formData, case_id: e.target.value })}
                    placeholder="e.g. 12"
                    className="w-full border rounded-lg p-2 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-semibold mb-1">Camera ID (optional)</label>
                  <input
                    type="number"
                    value={formData.camera_id}
                    onChange={(e) => setFormData({ ...formData, camera_id: e.target.value })}
                    placeholder="e.g. 4"
                    className="w-full border rounded-lg p-2 text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block text-gray-700 font-semibold mb-1">Evidence File (optional)</label>
                <input
                  type="file"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="w-full border rounded-lg p-2 text-xs bg-gray-50"
                  accept="image/jpeg,image/png,image/webp,video/mp4,application/pdf"
                />
                <span className="text-[10px] text-gray-400 mt-0.5 block">
                  Accepted: JPEG, PNG, WEBP, MP4, PDF. Max 2GB for video, 20MB for images.
                </span>
              </div>

              <div>
                <label className="block text-gray-700 font-semibold mb-1">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Official description of the evidence item..."
                  className="w-full border rounded-lg p-2 text-xs h-16"
                />
              </div>

              <div>
                <label className="block text-gray-700 font-semibold mb-1">Tags (comma-separated)</label>
                <input
                  type="text"
                  value={formData.tags}
                  onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                  placeholder="cctv, north_gate, suspect_jacket"
                  className="w-full border rounded-lg p-2 text-xs"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t">
                <button
                  type="button"
                  onClick={() => setUploadModalOpen(false)}
                  className="px-4 py-2 border rounded-lg text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploadLoading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-semibold rounded-lg"
                >
                  {uploadLoading ? 'Verifying & Ingesting...' : 'Ingest Record'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
