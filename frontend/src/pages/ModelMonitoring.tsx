/**
 * ModelMonitoring – Module 11 model & dataset registry management page.
 * 
 * Displays active AI models, model lifecycle management, dataset registry,
 * and drift monitoring. Admin-only operations (activate/retire) are gated.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Cpu, Database, RefreshCw, Plus, AlertTriangle,
  TrendingDown, CheckCircle2, FlaskConical,
} from 'lucide-react';
import ModelStatus from '../components/ModelStatus';
import DriftIndicator from '../components/DriftIndicator';
import {
  listModels, listDatasets, getDriftEvents,
  activateModel, retireModel, acknowledgeDriftEvent, runDriftCheck,
} from '../services/analyticsApi';
import type { ModelRegistryItem, DatasetRegistryItem, DriftEventItem } from '../types/analytics';

export default function ModelMonitoring() {
  const [models, setModels] = useState<ModelRegistryItem[]>([]);
  const [datasets, setDatasets] = useState<DatasetRegistryItem[]>([]);
  const [driftEvents, setDriftEvents] = useState<DriftEventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [driftChecking, setDriftChecking] = useState(false);
  const [activeTab, setActiveTab] = useState<'models' | 'datasets' | 'drift'>('models');

  const [isAdmin] = useState(() => {
    try {
      const token = localStorage.getItem('sentinex_token');
      if (!token) return false;
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.role === 'ADMIN';
    } catch { return false; }
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [m, d] = await Promise.all([listModels(), listDatasets()]);
      setModels(m);
      setDatasets(d);
      if (isAdmin) {
        const drifts = await getDriftEvents(30);
        setDriftEvents(drifts);
      }
    } catch { /* silent */ }
    setLoading(false);
  }, [isAdmin]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleActivate = async (id: number) => {
    try { const updated = await activateModel(id); setModels((prev) => prev.map((m) => m.id === id ? updated : m)); }
    catch { /* silent */ }
  };

  const handleRetire = async (id: number) => {
    if (!window.confirm('Retire this model? This action requires authorized human review.')) return;
    try { const updated = await retireModel(id); setModels((prev) => prev.map((m) => m.id === id ? updated : m)); }
    catch { /* silent */ }
  };

  const handleAcknowledgeDrift = async (eventId: number) => {
    try {
      const updated = await acknowledgeDriftEvent(eventId);
      setDriftEvents((prev) => prev.map((e) => e.id === eventId ? updated : e));
    } catch { /* silent */ }
  };

  const handleRunDriftCheck = async () => {
    setDriftChecking(true);
    try {
      const newEvents = await runDriftCheck();
      if (newEvents.length > 0) {
        setDriftEvents((prev) => [...newEvents, ...prev]);
      } else {
        alert('Drift check complete. No significant drift detected.');
      }
    } catch { /* silent */ }
    setDriftChecking(false);
  };

  const activeModels  = models.filter((m) => m.status === 'ACTIVE');
  const testingModels = models.filter((m) => m.status === 'TESTING');
  const retiredModels = models.filter((m) => m.status === 'RETIRED');
  const unackedDrift  = driftEvents.filter((e) => !e.is_acknowledged);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Cpu className="w-6 h-6 text-purple-600" />
            Model & Data Monitoring
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            AI model registry, dataset registry, and drift monitoring.
            Model/threshold changes require authorized human review.
          </p>
        </div>
        <button onClick={fetchData} disabled={loading} className="p-2 text-gray-400 hover:text-gray-600 rounded-lg">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white rounded-xl border-2 border-green-200 p-4 shadow-sm text-center">
          <div className="text-2xl font-bold text-green-700">{activeModels.length}</div>
          <div className="text-xs font-semibold text-green-600 mt-1 flex items-center justify-center gap-1"><CheckCircle2 className="w-3 h-3" /> Active Models</div>
        </div>
        <div className="bg-white rounded-xl border-2 border-yellow-200 p-4 shadow-sm text-center">
          <div className="text-2xl font-bold text-yellow-700">{testingModels.length}</div>
          <div className="text-xs font-semibold text-yellow-600 mt-1 flex items-center justify-center gap-1"><FlaskConical className="w-3 h-3" /> In Testing</div>
        </div>
        <div className="bg-white rounded-xl border-2 border-blue-200 p-4 shadow-sm text-center">
          <div className="text-2xl font-bold text-blue-700">{datasets.length}</div>
          <div className="text-xs font-semibold text-blue-600 mt-1 flex items-center justify-center gap-1"><Database className="w-3 h-3" /> Datasets</div>
        </div>
        <div className={`bg-white rounded-xl border-2 p-4 shadow-sm text-center ${unackedDrift.length > 0 ? 'border-red-200' : 'border-gray-200'}`}>
          <div className={`text-2xl font-bold ${unackedDrift.length > 0 ? 'text-red-700' : 'text-gray-400'}`}>{unackedDrift.length}</div>
          <div className={`text-xs font-semibold mt-1 flex items-center justify-center gap-1 ${unackedDrift.length > 0 ? 'text-red-600' : 'text-gray-400'}`}>
            <TrendingDown className="w-3 h-3" /> Drift Events
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4">
          {([
            { id: 'models', label: 'Model Registry', count: models.length },
            { id: 'datasets', label: 'Dataset Registry', count: datasets.length },
            ...(isAdmin ? [{ id: 'drift', label: 'Drift Monitoring', count: unackedDrift.length }] : []),
          ] as { id: 'models' | 'datasets' | 'drift'; label: string; count: number }[]).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-700'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
              {tab.count > 0 && (
                <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full ${
                  activeTab === tab.id ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'
                }`}>{tab.count}</span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Model Registry tab */}
      {activeTab === 'models' && (
        <div className="space-y-4">
          {activeModels.length > 0 && (
            <section>
              <h3 className="text-xs font-bold text-green-600 uppercase tracking-wider mb-3">Active Models</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {activeModels.map((m) => (
                  <ModelStatus key={m.id} model={m} isAdmin={isAdmin} onRetire={handleRetire} />
                ))}
              </div>
            </section>
          )}
          {testingModels.length > 0 && (
            <section>
              <h3 className="text-xs font-bold text-yellow-600 uppercase tracking-wider mb-3">Testing Phase</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {testingModels.map((m) => (
                  <ModelStatus key={m.id} model={m} isAdmin={isAdmin} onActivate={handleActivate} onRetire={handleRetire} />
                ))}
              </div>
            </section>
          )}
          {retiredModels.length > 0 && (
            <section>
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Retired Models</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {retiredModels.map((m) => (
                  <ModelStatus key={m.id} model={m} isAdmin={false} />
                ))}
              </div>
            </section>
          )}
          {models.length === 0 && !loading && (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
              No models registered yet. {isAdmin && (
                <button className="ml-1 text-blue-600 hover:underline inline-flex items-center gap-1">
                  <Plus className="w-3 h-3" /> Register via API
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Dataset Registry tab */}
      {activeTab === 'datasets' && (
        <div>
          {datasets.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
              No datasets registered. Only authorized, consented, synthetic, or licensed data may be registered.
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      {['Dataset', 'Version', 'Category', 'Source', 'Samples', 'Registered'].map((h) => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {datasets.map((ds) => (
                      <tr key={ds.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3">
                          <p className="font-medium text-gray-800">{ds.dataset_name}</p>
                          {ds.notes && <p className="text-xs text-gray-400 mt-0.5 max-w-xs truncate">{ds.notes}</p>}
                        </td>
                        <td className="px-4 py-3"><code className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded">{ds.dataset_version}</code></td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                            ds.category === 'TEST' ? 'bg-red-50 text-red-700' :
                            ds.category === 'VALIDATION' ? 'bg-yellow-50 text-yellow-700' :
                            'bg-blue-50 text-blue-700'
                          }`}>{ds.category}</span>
                        </td>
                        <td className="px-4 py-3 text-gray-600">{ds.source_type}</td>
                        <td className="px-4 py-3 text-gray-600">{ds.sample_count?.toLocaleString() ?? '—'}</td>
                        <td className="px-4 py-3 text-xs text-gray-400">{new Date(ds.registered_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-xs text-yellow-800">
              <strong>Policy:</strong> Only authorized, consented, synthetic, or legitimately licensed research data may be registered.
              TEST datasets must not be used for continuous threshold tuning.
            </p>
          </div>
        </div>
      )}

      {/* Drift Monitoring tab */}
      {activeTab === 'drift' && isAdmin && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">
                Drift events are technical monitoring signals. They do NOT automatically trigger model retraining or threshold changes.
                Authorized human/researcher review is required.
              </p>
            </div>
            <button
              onClick={handleRunDriftCheck}
              disabled={driftChecking}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${driftChecking ? 'animate-spin' : ''}`} />
              Run Drift Check
            </button>
          </div>

          {driftEvents.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
              <AlertTriangle className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-400">No drift events detected.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {driftEvents.map((evt) => (
                <DriftIndicator
                  key={evt.id}
                  event={evt}
                  isAdmin={isAdmin}
                  onAcknowledge={handleAcknowledgeDrift}
                />
              ))}
            </div>
          )}

          <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
            <p className="text-xs text-gray-500">
              <strong>Research Note:</strong> Drift monitoring compares the current week against the prior week.
              Significant changes are flagged for human review. No automated model changes are made.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
