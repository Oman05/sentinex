import { useEffect, useState } from 'react';
import { Sliders, Save, History, RotateCw, Check } from 'lucide-react';
import {
  getSystemConfigs,
  updateSystemConfigs,
  getConfigAuditHistory,
} from '../services/adminApi';
import type { SystemConfigItem, SystemConfigAuditItem } from '../types/admin';

export default function AdminSystemConfig() {
  const [configs, setConfigs] = useState<SystemConfigItem[]>([]);
  const [auditTrail, setAuditTrail] = useState<SystemConfigAuditItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>('ALL');
  const [editedValues, setEditedValues] = useState<{ [key: string]: any }>({});
  const [changeReasons, setChangeReasons] = useState<{ [key: string]: string }>({});
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const fetchConfigs = async () => {
    setLoading(true);
    try {
      const [allConfigs, audits] = await Promise.all([
        getSystemConfigs(),
        getConfigAuditHistory(25),
      ]);
      setConfigs(allConfigs);
      setAuditTrail(audits);
      setEditedValues({});
      setChangeReasons({});
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to load configuration parameters');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfigs();
  }, []);

  const categories = ['ALL', ...Array.from(new Set(configs.map((c) => c.category)))];

  const filteredConfigs = activeCategory === 'ALL'
    ? configs
    : configs.filter((c) => c.category === activeCategory);

  const handleValueChange = (key: string, val: any) => {
    setEditedValues((prev) => ({ ...prev, [key]: val }));
  };

  const handleReasonChange = (key: string, reason: string) => {
    setChangeReasons((prev) => ({ ...prev, [key]: reason }));
  };

  const handleSaveItem = async (item: SystemConfigItem) => {
    const newValue = editedValues[item.key];
    const reason = changeReasons[item.key];

    if (newValue === undefined) {
      alert('No modifications made to save.');
      return;
    }
    if (!reason || reason.trim().length < 3) {
      alert('An audit justification / reason (min 3 characters) is required to alter system parameters.');
      return;
    }

    setSaving(true);
    setStatusMessage(null);
    try {
      await updateSystemConfigs([
        {
          key: item.key,
          value: newValue,
          reason: reason.trim(),
        },
      ]);
      setStatusMessage(`Successfully updated ${item.key}`);
      fetchConfigs();
    } catch (err: any) {
      alert(err?.response?.data?.detail?.errors?.[0]?.error || 'Failed to update configuration parameter');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Sliders className="w-6 h-6 text-blue-600" />
            Centralized System Configuration &amp; Parameter Tuning
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Audit-tracked AI thresholds, face quality gates, frame sampling intervals, and security policies.
          </p>
        </div>
        <button
          onClick={fetchConfigs}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition"
        >
          <RotateCw className="w-4 h-4" />
          Reload
        </button>
      </div>

      {statusMessage && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded text-sm flex items-center gap-2">
          <Check className="w-4 h-4" />
          {statusMessage}
        </div>
      )}

      {/* Category Tabs */}
      <div className="flex space-x-2 border-b border-gray-200 pb-2 overflow-x-auto">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition whitespace-nowrap ${
              activeCategory === cat
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Configurations List */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden divide-y divide-gray-100">
        {loading ? (
          <div className="p-10 text-center text-gray-500">
            <RotateCw className="w-6 h-6 animate-spin mx-auto text-blue-600" />
          </div>
        ) : filteredConfigs.length === 0 ? (
          <div className="p-10 text-center text-gray-500">No configuration items available.</div>
        ) : (
          filteredConfigs.map((item) => {
            const isDirty = editedValues[item.key] !== undefined && editedValues[item.key] !== item.value;
            const currentVal = editedValues[item.key] !== undefined ? editedValues[item.key] : item.value;

            return (
              <div key={item.key} className="p-5 hover:bg-gray-50/50 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="max-w-xl">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold text-gray-900">{item.key}</span>
                    <span className="px-2 py-0.5 text-[10px] font-semibold bg-gray-100 text-gray-600 rounded">
                      {item.category}
                    </span>
                    {item.requires_restart && (
                      <span className="px-2 py-0.5 text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200 rounded">
                        Requires Restart
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{item.description || 'No description provided.'}</p>
                </div>

                <div className="flex flex-col sm:flex-row items-end sm:items-center gap-3">
                  {/* Input by type */}
                  {item.value_type === 'bool' ? (
                    <select
                      value={String(currentVal)}
                      onChange={(e) => handleValueChange(item.key, e.target.value === 'true')}
                      className="border border-gray-300 rounded px-3 py-1 text-sm bg-white"
                    >
                      <option value="true">true (Enabled)</option>
                      <option value="false">false (Disabled)</option>
                    </select>
                  ) : (
                    <input
                      type={item.value_type === 'int' || item.value_type === 'float' ? 'number' : 'text'}
                      step={item.value_type === 'float' ? '0.01' : '1'}
                      value={currentVal}
                      onChange={(e) => handleValueChange(item.key, e.target.value)}
                      className="border border-gray-300 rounded px-3 py-1 text-sm w-36 font-mono"
                    />
                  )}

                  {/* Justification input */}
                  {isDirty && (
                    <input
                      type="text"
                      placeholder="Audit justification..."
                      value={changeReasons[item.key] || ''}
                      onChange={(e) => handleReasonChange(item.key, e.target.value)}
                      className="border border-amber-300 bg-amber-50/30 rounded px-2.5 py-1 text-xs w-48"
                    />
                  )}

                  <button
                    onClick={() => handleSaveItem(item)}
                    disabled={!isDirty || saving}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold transition ${
                      isDirty
                        ? 'bg-blue-600 text-white hover:bg-blue-700 cursor-pointer shadow-sm'
                        : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    }`}
                  >
                    <Save className="w-3.5 h-3.5" />
                    Save
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Configuration Audit Trail */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
            <History className="w-4 h-4 text-blue-600" />
            Configuration Change Audit Trail
          </h2>
          <span className="text-xs text-gray-400">Strict Accountability Record</span>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-xs">
            <thead className="bg-gray-50 text-gray-600 uppercase font-semibold">
              <tr>
                <th className="px-6 py-2.5 text-left">Setting Key</th>
                <th className="px-6 py-2.5 text-left">Previous Value</th>
                <th className="px-6 py-2.5 text-left">New Value</th>
                <th className="px-6 py-2.5 text-left">Justification / Reason</th>
                <th className="px-6 py-2.5 text-left">Changed Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {auditTrail.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-6 text-center text-gray-400">
                    No configuration changes recorded in this session.
                  </td>
                </tr>
              ) : (
                auditTrail.map((a) => (
                  <tr key={a.id} className="hover:bg-gray-50 font-mono">
                    <td className="px-6 py-3 font-semibold text-gray-900">{a.key}</td>
                    <td className="px-6 py-3 text-red-600 line-through">{a.old_value || 'None'}</td>
                    <td className="px-6 py-3 text-green-700 font-bold">{a.new_value}</td>
                    <td className="px-6 py-3 text-gray-700 font-sans">{a.reason || 'N/A'}</td>
                    <td className="px-6 py-3 text-gray-400 font-sans">{new Date(a.changed_at).toLocaleString()}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
