/**
 * EvaluationDashboard – Module 11 AI Evaluation & Research Dashboard
 * 
 * Provides:
 * - Controlled evaluation run creation & execution
 * - Confusion Matrix display (TP, FP, TN, FN)
 * - Research metrics (Precision, Recall, F1, FMR, FNMR, Top-1, Top-5)
 * - Experimental Threshold Evaluation tool
 * - Similarity score distribution analysis
 * - Research evaluation report generation & export
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical, Play, FileText, Download, Sliders,
  RefreshCw, Plus, X, BarChart2, ShieldAlert
} from 'lucide-react';
import EvaluationTable from '../components/EvaluationTable';
import ConfusionMatrix from '../components/ConfusionMatrix';
import MetricCard from '../components/MetricCard';
import {
  listEvaluationRuns,
  createEvaluationRun,
  executeEvaluationRun,
  getEvaluationResults,
  evaluateThreshold,
  getScoreDistribution,
  generateResearchReport,
  listModels,
  listDatasets,
} from '../services/analyticsApi';
import type {
  EvaluationRunItem,
  EvaluationResultItem,
  EvaluationRunCreate,
  ThresholdEvaluationResult,
  ScoreDistributionResponse,
  ModelRegistryItem,
  DatasetRegistryItem,
} from '../types/analytics';

export default function EvaluationDashboard() {
  const [runs, setRuns] = useState<EvaluationRunItem[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [activeResults, setActiveResults] = useState<EvaluationResultItem | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [loadingResults, setLoadingResults] = useState(false);
  const [models, setModels] = useState<ModelRegistryItem[]>([]);
  const [datasets, setDatasets] = useState<DatasetRegistryItem[]>([]);

  // Create Run Modal
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState<EvaluationRunCreate>({
    run_name: '',
    model_name: '',
    model_version: '',
    dataset_name: '',
    dataset_version: '',
    threshold: 0.70,
    justification: '',
    notes: '',
  });
  const [creatingRun, setCreatingRun] = useState(false);

  // Threshold Evaluation tool
  const [testThreshold, setTestThreshold] = useState<number>(0.70);
  const [thresholdResult, setThresholdResult] = useState<ThresholdEvaluationResult | null>(null);
  const [evaluatingThreshold, setEvaluatingThreshold] = useState(false);

  // Score distribution
  const [scoreDist, setScoreDist] = useState<ScoreDistributionResponse | null>(null);

  // Load runs & registries
  const loadData = useCallback(async () => {
    setLoadingRuns(true);
    try {
      const [runsData, mData, dData, sDist] = await Promise.all([
        listEvaluationRuns(),
        listModels(),
        listDatasets(),
        getScoreDistribution('30d'),
      ]);
      setRuns(runsData);
      setModels(mData);
      setDatasets(dData);
      setScoreDist(sDist);

      // Auto-select latest completed run if available
      const completed = runsData.find((r) => r.status === 'COMPLETED');
      if (completed && !selectedRunId) {
        setSelectedRunId(completed.run_id);
        fetchResults(completed.run_id);
      }
    } catch (err) {
      console.error('Failed to load evaluation runs:', err);
    } finally {
      setLoadingRuns(false);
    }
  }, [selectedRunId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const fetchResults = async (runId: string) => {
    setLoadingResults(true);
    try {
      const res = await getEvaluationResults(runId);
      setActiveResults(res);
      setSelectedRunId(runId);
    } catch {
      setActiveResults(null);
    } finally {
      setLoadingResults(false);
    }
  };

  const handleExecute = async (runId: string) => {
    try {
      const res = await executeEvaluationRun(runId);
      setActiveResults(res);
      setSelectedRunId(runId);
      // Refresh list status
      const updated = await listEvaluationRuns();
      setRuns(updated);
    } catch (err) {
      console.error('Execution failed:', err);
      alert('Failed to execute evaluation run.');
    }
  };

  const handleCreateRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.model_name || !formData.dataset_name) {
      alert('Please select or specify a model and dataset.');
      return;
    }
    setCreatingRun(true);
    try {
      const newRun = await createEvaluationRun(formData);
      setShowModal(false);
      setFormData({
        run_name: '',
        model_name: '',
        model_version: '',
        dataset_name: '',
        dataset_version: '',
        threshold: 0.70,
        justification: '',
        notes: '',
      });
      const updated = await listEvaluationRuns();
      setRuns(updated);
      setSelectedRunId(newRun.run_id);
    } catch (err) {
      console.error('Failed to create run:', err);
      alert('Failed to create evaluation run.');
    } finally {
      setCreatingRun(false);
    }
  };

  const handleThresholdTest = async () => {
    setEvaluatingThreshold(true);
    try {
      const res = await evaluateThreshold(testThreshold, '30d');
      setThresholdResult(res);
    } catch (err) {
      console.error('Threshold test failed:', err);
    } finally {
      setEvaluatingThreshold(false);
    }
  };

  const handleDownloadReport = async (runId: string) => {
    try {
      const report = await generateResearchReport(runId);
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `research_report_${runId}_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Report export failed:', err);
      alert('Failed to generate research report.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <FlaskConical className="w-6 h-6 text-purple-600" />
            AI Evaluation & Research Engine
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Controlled evaluation runs, confusion matrix, precision/recall, retrieval metrics, and threshold tuning.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={loadingRuns}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loadingRuns ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" /> New Evaluation Run
          </button>
        </div>
      </div>

      {/* Evaluation Runs Table */}
      <section className="space-y-3">
        <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider">Evaluation Runs</h2>
        <EvaluationTable
          runs={runs}
          isLoading={loadingRuns}
          onExecute={handleExecute}
          onViewResults={fetchResults}
        />
      </section>

      {/* Selected Run Details & Confusion Matrix */}
      {selectedRunId && (
        <section className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
              <FileText className="w-4 h-4" /> Results for Run: <span className="font-mono text-blue-700">{selectedRunId}</span>
            </h2>
            {activeResults && (
              <button
                onClick={() => handleDownloadReport(selectedRunId)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 rounded-lg transition-colors shadow-sm"
              >
                <Download className="w-3.5 h-3.5" /> Export Research Report (JSON)
              </button>
            )}
          </div>

          {loadingResults ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500 text-sm">
              Loading metrics for {selectedRunId}...
            </div>
          ) : activeResults ? (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2">
                <ConfusionMatrix
                  tp={activeResults.true_positives}
                  fp={activeResults.false_positives}
                  tn={activeResults.true_negatives}
                  fn={activeResults.false_negatives}
                  precision={activeResults.precision}
                  recall={activeResults.recall}
                  f1Score={activeResults.f1_score}
                  fmr={activeResults.false_match_rate}
                  fnmr={activeResults.false_non_match_rate}
                  disclaimer={activeResults.disclaimer}
                />
              </div>

              {/* Retrieval & Latency Metrics */}
              <div className="space-y-3">
                <MetricCard
                  label="Top-1 Accuracy"
                  value={activeResults.top1_accuracy !== null ? `${(activeResults.top1_accuracy * 100).toFixed(1)}%` : '—'}
                  color="green"
                  description="Correct identity retrieved at rank 1"
                />
                <MetricCard
                  label="Top-5 Retrieval Rate"
                  value={activeResults.top5_retrieval_rate !== null ? `${(activeResults.top5_retrieval_rate * 100).toFixed(1)}%` : '—'}
                  color="blue"
                  description="Correct identity in top 5 candidates"
                />
                <MetricCard
                  label="Avg Similarity Score"
                  value={activeResults.average_similarity_score !== null ? activeResults.average_similarity_score.toFixed(3) : '—'}
                  color="purple"
                  description="Mean cosine similarity of matches"
                />
                <MetricCard
                  label="Search Latency"
                  value={activeResults.average_latency_ms !== null ? `${activeResults.average_latency_ms.toFixed(1)} ms` : '—'}
                  color="gray"
                  description="Average vector retrieval time"
                />
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 p-6 text-center text-gray-500 text-sm">
              No results available for this run. Click <span className="font-semibold text-blue-600">Execute</span> in the table above to compute evaluation metrics.
            </div>
          )}
        </section>
      )}

      {/* Threshold Evaluation Experiment Tool */}
      <section className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <Sliders className="w-5 h-5 text-blue-600" />
              Experimental Threshold Evaluation Tool
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Simulate candidate matching threshold behavior on recent data. Do NOT automatically adjust production thresholds based on this tool.
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-center gap-4 bg-gray-50 p-4 rounded-lg border border-gray-200">
          <div className="flex-1 w-full">
            <div className="flex justify-between text-xs font-semibold text-gray-700 mb-1">
              <span>Similarity Threshold: <strong className="text-blue-600 font-mono text-sm">{testThreshold.toFixed(2)}</strong></span>
              <span className="text-gray-400">0.00 – 1.00</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.95"
              step="0.01"
              value={testThreshold}
              onChange={(e) => setTestThreshold(parseFloat(e.target.value))}
              className="w-full accent-blue-600"
            />
          </div>
          <button
            onClick={handleThresholdTest}
            disabled={evaluatingThreshold}
            className="w-full sm:w-auto px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors flex items-center justify-center gap-1.5"
          >
            <Play className={`w-3.5 h-3.5 ${evaluatingThreshold ? 'animate-spin' : ''}`} />
            Evaluate Threshold
          </button>
        </div>

        {thresholdResult && (
          <div className="space-y-3 pt-2">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <MetricCard
                label="Evaluated Matches"
                value={thresholdResult.total_matches_evaluated}
                color="blue"
              />
              <MetricCard
                label="Estimated FMR"
                value={thresholdResult.estimated_fmr !== null ? `${(thresholdResult.estimated_fmr * 100).toFixed(2)}%` : '—'}
                color={thresholdResult.estimated_fmr && thresholdResult.estimated_fmr > 0.05 ? 'red' : 'green'}
                description="False Match Rate"
              />
              <MetricCard
                label="Estimated FNMR"
                value={thresholdResult.estimated_fnmr !== null ? `${(thresholdResult.estimated_fnmr * 100).toFixed(2)}%` : '—'}
                color={thresholdResult.estimated_fnmr && thresholdResult.estimated_fnmr > 0.1 ? 'yellow' : 'blue'}
                description="False Non-Match Rate"
              />
              <MetricCard
                label="Estimated Precision"
                value={thresholdResult.estimated_precision !== null ? `${(thresholdResult.estimated_precision * 100).toFixed(1)}%` : '—'}
                color="purple"
              />
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-100">
              <div>Confirmed Above: <strong>{thresholdResult.confirmed_above}</strong></div>
              <div>Rejected Above (FP): <strong className="text-red-600">{thresholdResult.rejected_above}</strong></div>
              <div>Confirmed Below (FN): <strong className="text-yellow-600">{thresholdResult.confirmed_below}</strong></div>
              <div>Rejected Below: <strong>{thresholdResult.rejected_below}</strong></div>
            </div>
          </div>
        )}
      </section>

      {/* Similarity Score Distribution */}
      {scoreDist && (
        <section className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-purple-600" /> Score Distribution (Genuine vs Non-Match Pairs)
            </h2>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricCard label="Genuine Pairs" value={scoreDist.total_genuine} color="green" />
            <MetricCard label="Avg Genuine Score" value={scoreDist.avg_genuine_score !== null ? scoreDist.avg_genuine_score.toFixed(3) : '—'} color="green" />
            <MetricCard label="Non-Match Pairs" value={scoreDist.total_non_match} color="red" />
            <MetricCard label="Avg Non-Match Score" value={scoreDist.avg_non_match_score !== null ? scoreDist.avg_non_match_score.toFixed(3) : '—'} color="red" />
          </div>
          <p className="text-xs text-gray-400 italic">
            Genuine scores are verified from confirmed human review actions. Non-match scores originate from rejected candidate alerts. Do not treat raw similarity scores as guaranteed probabilities.
          </p>
        </section>
      )}

      {/* Research Disclaimer Banner */}
      <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-amber-800 leading-relaxed">
          <strong>Research Evaluation Principle:</strong> Results are specific to the evaluated dataset, camera conditions,
          model version, and experimental configuration and should not automatically be generalized to other populations
          or deployment environments. Operational decisions must always involve human examiner verification.
        </p>
      </div>

      {/* Create Run Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-lg font-bold text-gray-900">Create New Evaluation Run</h3>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateRun} className="space-y-4 text-sm">
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">Run Name</label>
                <input
                  type="text"
                  placeholder="e.g. EVAL-RESNET50-TEST-V1"
                  value={formData.run_name || ''}
                  onChange={(e) => setFormData({ ...formData, run_name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">Model Name *</label>
                  {models.length > 0 ? (
                    <select
                      value={formData.model_name}
                      onChange={(e) => {
                        const m = models.find((mod) => mod.model_name === e.target.value);
                        setFormData({
                          ...formData,
                          model_name: e.target.value,
                          model_version: m ? m.version : formData.model_version,
                          model_registry_id: m ? m.id : undefined,
                        });
                      }}
                      className="w-full px-3 py-2 border rounded-lg bg-white"
                      required
                    >
                      <option value="">Select Model</option>
                      {models.map((m) => (
                        <option key={m.id} value={m.model_name}>
                          {m.model_name} (v{m.version})
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      placeholder="e.g. FACE_EMBEDDING_V1"
                      value={formData.model_name}
                      onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                      className="w-full px-3 py-2 border rounded-lg"
                      required
                    />
                  )}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">Model Version</label>
                  <input
                    type="text"
                    placeholder="e.g. 1.0.0"
                    value={formData.model_version}
                    onChange={(e) => setFormData({ ...formData, model_version: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">Dataset Name *</label>
                  {datasets.length > 0 ? (
                    <select
                      value={formData.dataset_name}
                      onChange={(e) => {
                        const d = datasets.find((ds) => ds.dataset_name === e.target.value);
                        setFormData({
                          ...formData,
                          dataset_name: e.target.value,
                          dataset_version: d ? d.dataset_version : formData.dataset_version,
                          dataset_registry_id: d ? d.id : undefined,
                        });
                      }}
                      className="w-full px-3 py-2 border rounded-lg bg-white"
                      required
                    >
                      <option value="">Select Dataset</option>
                      {datasets.map((d) => (
                        <option key={d.id} value={d.dataset_name}>
                          {d.dataset_name} ({d.category})
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      placeholder="e.g. SYNTHETIC_TEST_V1"
                      value={formData.dataset_name}
                      onChange={(e) => setFormData({ ...formData, dataset_name: e.target.value })}
                      className="w-full px-3 py-2 border rounded-lg"
                      required
                    />
                  )}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">Dataset Version</label>
                  <input
                    type="text"
                    placeholder="e.g. 1.0"
                    value={formData.dataset_version}
                    onChange={(e) => setFormData({ ...formData, dataset_version: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">Threshold (0.0 - 1.0)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.0"
                  max="1.0"
                  value={formData.threshold || 0.70}
                  onChange={(e) => setFormData({ ...formData, threshold: parseFloat(e.target.value) })}
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">Justification</label>
                <textarea
                  placeholder="Rationale for selected dataset, model, and threshold..."
                  value={formData.justification || ''}
                  onChange={(e) => setFormData({ ...formData, justification: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg resize-none h-16"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingRun}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow-sm"
                >
                  {creatingRun ? 'Creating...' : 'Create Run'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
