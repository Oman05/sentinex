import React, { useEffect, useState } from 'react';
import { Archive, Plus, CheckCircle2, AlertTriangle, RotateCw } from 'lucide-react';
import {
  listBackups,
  createBackup,
  verifyBackup,
  restoreBackup,
} from '../services/adminApi';
import type { BackupItem } from '../types/admin';

export default function AdminBackupManagement() {
  const [backups, setBackups] = useState<BackupItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);

  // Restore Modal State
  const [showRestoreModal, setShowRestoreModal] = useState(false);
  const [selectedBackup, setSelectedBackup] = useState<BackupItem | null>(null);
  const [confirmationCode, setConfirmationCode] = useState('');
  const [restoring, setRestoring] = useState(false);

  // Create Backup state
  const [backupType, setBackupType] = useState('FULL');
  const [backupNotes, setBackupNotes] = useState('');

  const fetchBackups = async () => {
    setLoading(true);
    try {
      const data = await listBackups();
      setBackups(data);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to load backup records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBackups();
  }, []);

  const handleCreateBackup = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await createBackup(backupType, backupNotes || 'Manual administrative snapshot');
      setBackupNotes('');
      fetchBackups();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to create backup');
    } finally {
      setCreating(false);
    }
  };

  const handleVerify = async (backupId: string) => {
    setVerifyingId(backupId);
    try {
      const res = await verifyBackup(backupId);
      alert(`Verification result: ${res.status}. ${res.details}`);
      fetchBackups();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Verification request failed');
    } finally {
      setVerifyingId(null);
    }
  };

  const handleRestore = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBackup) return;
    if (confirmationCode !== 'CONFIRM_RESTORE') {
      alert("You must type 'CONFIRM_RESTORE' in all caps to initiate system state recovery.");
      return;
    }

    setRestoring(true);
    try {
      await restoreBackup(selectedBackup.backup_id, confirmationCode);
      alert(`System restore completed successfully from archive ${selectedBackup.backup_id}`);
      setShowRestoreModal(false);
      setConfirmationCode('');
      fetchBackups();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Restore failed');
    } finally {
      setRestoring(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Archive className="w-6 h-6 text-blue-600" />
            System Backup, Verification &amp; Disaster Recovery
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Generate cryptographically signed (SHA-256) point-in-time archives of the database, model configs, and audit trails.
          </p>
        </div>
      </div>

      {/* Backup Creation Card */}
      <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm space-y-4">
        <h2 className="text-base font-semibold text-gray-900">Initiate Point-in-Time Archive</h2>
        <form onSubmit={handleCreateBackup} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-xs font-semibold text-gray-700">Backup Type</label>
            <select
              value={backupType}
              onChange={(e) => setBackupType(e.target.value)}
              className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm bg-white"
            >
              <option value="FULL">FULL (Database, Configs &amp; Metadata)</option>
              <option value="DATABASE">DATABASE (Database Snapshot Only)</option>
              <option value="CONFIG">CONFIG (System Configuration Metadata)</option>
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-semibold text-gray-700">Notes / Scope Justification</label>
            <input
              type="text"
              placeholder="e.g. Scheduled snapshot before production update"
              value={backupNotes}
              onChange={(e) => setBackupNotes(e.target.value)}
              className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={creating}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white font-medium rounded hover:bg-blue-700 transition disabled:opacity-50 text-sm"
          >
            {creating ? <RotateCw className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Create Snapshot
          </button>
        </form>
      </div>

      {/* Backups Table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-gray-600 text-xs uppercase font-semibold">
            <tr>
              <th className="px-6 py-3 text-left">Archive ID &amp; File</th>
              <th className="px-6 py-3 text-left">Type</th>
              <th className="px-6 py-3 text-left">Size</th>
              <th className="px-6 py-3 text-left">SHA-256 Integrity</th>
              <th className="px-6 py-3 text-left">Verification Status</th>
              <th className="px-6 py-3 text-left">Created At</th>
              <th className="px-6 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-6 py-10 text-center">
                  <RotateCw className="w-6 h-6 animate-spin mx-auto text-blue-600" />
                </td>
              </tr>
            ) : backups.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-10 text-center text-gray-500">
                  No system backups generated yet.
                </td>
              </tr>
            ) : (
              backups.map((b) => {
                const isVerified = b.verification_status === 'VERIFIED';
                return (
                  <tr key={b.backup_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="font-bold text-gray-900 font-mono text-xs">{b.backup_id}</div>
                      <div className="text-xs text-gray-500">{b.filename}</div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-gray-100 text-gray-800">
                        {b.backup_type}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-600 text-xs">
                      {(b.size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td className="px-6 py-4 font-mono text-[11px] text-gray-400">
                      {b.checksum_sha256.slice(0, 16)}...
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold ${
                          isVerified ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {isVerified ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
                        ) : (
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                        )}
                        {b.verification_status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-500 text-xs">
                      {new Date(b.created_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <button
                        onClick={() => handleVerify(b.backup_id)}
                        disabled={verifyingId === b.backup_id}
                        className="text-xs font-medium text-blue-600 hover:text-blue-800"
                        title="Run SHA-256 Checksum Verification"
                      >
                        {verifyingId === b.backup_id ? 'Verifying...' : 'Verify'}
                      </button>
                      <button
                        onClick={() => {
                          setSelectedBackup(b);
                          setShowRestoreModal(true);
                        }}
                        className="text-xs font-medium text-red-600 hover:text-red-800 ml-2"
                        title="Initiate Restore"
                      >
                        Restore
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Restore Confirmation Modal */}
      {showRestoreModal && selectedBackup && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-red-700 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-600" />
              Confirm System State Restore
            </h2>
            <p className="text-sm text-gray-600">
              Restoring archive <span className="font-mono font-bold text-gray-900">{selectedBackup.backup_id}</span> will replace current database state with the archive snapshot.
            </p>
            <div className="bg-red-50 p-3 rounded text-xs text-red-800 border border-red-200">
              Type <span className="font-mono font-bold">CONFIRM_RESTORE</span> below to verify authorized human intent.
            </div>
            <form onSubmit={handleRestore} className="space-y-3">
              <div>
                <input
                  type="text"
                  required
                  placeholder="CONFIRM_RESTORE"
                  value={confirmationCode}
                  onChange={(e) => setConfirmationCode(e.target.value)}
                  className="w-full border border-red-300 rounded px-3 py-2 text-sm font-mono"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-4 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowRestoreModal(false)}
                  className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={confirmationCode !== 'CONFIRM_RESTORE' || restoring}
                  className="px-4 py-2 text-sm bg-red-600 text-white font-medium rounded hover:bg-red-700 disabled:opacity-50"
                >
                  {restoring ? 'Restoring System...' : 'Execute Recovery'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
