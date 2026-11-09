/**
 * AnalyticsDashboard – Module 11 main analytics overview page.
 * 
 * Shows aggregated system metrics across all pipeline stages.
 * ALL metrics are aggregated statistics only — no personal data is displayed.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Camera, LayoutDashboard, Cpu, Users, Bell, FolderLock, RefreshCw,
  Download, TrendingUp, CheckCircle2, XCircle, Activity,
} from 'lucide-react';
import MetricCard from '../components/MetricCard';
import PerformanceChart from '../components/PerformanceChart';
import {
  getOverview,
  exportAnalyticsCSV,
  exportAnalyticsJSON,
} from '../services/analyticsApi';
import type { OverviewResponse, TimeRange } from '../types/analytics';

const TIME_RANGES: { label: string; value: TimeRange }[] = [
  { label: 'Today',     value: 'today' },
  { label: 'Last 7 Days', value: '7d'  },
  { label: 'Last 30 Days', value: '30d' },
];

function fmtMs(ms: number | null): string {
  if (ms === null) return '—';
  return `${ms.toFixed(1)} ms`;
}

function fmtPct(v: number | null): string {
  if (v === null) return '—';
  return `${(v * 100).toFixed(2)}%`;
}

function fmtSec(s: number | null): string {
  if (s === null) return '—';
  if (s < 60) return `${s.toFixed(0)}s`;
  return `${(s / 60).toFixed(1)} min`;
}

export default function AnalyticsDashboard() {
  const [timeRange, setTimeRange] = useState<TimeRange>('7d');
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getOverview(timeRange);
      setData(result);
    } catch {
      setError('Failed to load analytics. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [timeRange]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleExportCSV = async () => {
    setExporting(true);
    try {
      const blob = await exportAnalyticsCSV(timeRange);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sentinex_analytics_${timeRange}_${new Date().toISOString().slice(0,10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* silent */ }
    setExporting(false);
  };

  const handleExportJSON = async () => {
    setExporting(true);
    try {
      const jsonData = await exportAnalyticsJSON(timeRange);
      const blob = new Blob([JSON.stringify(jsonData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sentinex_analytics_${timeRange}_${new Date().toISOString().slice(0,10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* silent */ }
    setExporting(false);
  };

  const pipelineChartItems = data?.pipeline.map((s) => ({
    label: s.stage_name.replace(/_/g, ' '),
    value: s.successful_count,
    maxValue: s.input_count,
    color: s.failed_count > 0 ? 'bg-orange-400' : 'bg-blue-500',
  })) ?? [];

  const rejectionItems = data
    ? Object.entries(data.pipeline.length ? {} : {}).map(([k, v]) => ({
        label: k.replace(/_/g, ' '),
        value: v as number,
        color: 'bg-red-400',
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <LayoutDashboard className="w-6 h-6 text-blue-600" />
            OMYRA — System Analytics
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Aggregated system performance metrics. All values are statistical summaries — no personal data.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Time range selector */}
          <div className="flex bg-gray-100 rounded-lg p-0.5 gap-0.5">
            {TIME_RANGES.map((tr) => (
              <button
                key={tr.value}
                onClick={() => setTimeRange(tr.value)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                  timeRange === tr.value
                    ? 'bg-white text-blue-700 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {tr.label}
              </button>
            ))}
          </div>

          <button
            onClick={fetchData}
            disabled={loading}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          {/* Export buttons */}
          <div className="flex gap-1">
            <button
              onClick={handleExportCSV}
              disabled={exporting || !data}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-white border border-gray-200 hover:bg-gray-50 text-gray-600 rounded-lg transition-colors disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5" /> CSV
            </button>
            <button
              onClick={handleExportJSON}
              disabled={exporting || !data}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-white border border-gray-200 hover:bg-gray-50 text-gray-600 rounded-lg transition-colors disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5" /> JSON
            </button>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">{error}</div>
      )}

      {/* Loading skeleton */}
      {loading && !data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="bg-gray-100 rounded-xl h-24 animate-pulse" />
          ))}
        </div>
      )}

      {/* ─── System Health ─────────────────────────────────────────────── */}
      {data && (
        <>
          <section>
            <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4" /> System Health
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              <MetricCard label="Cameras Online"  value={data.system.cameras_online}  icon={Camera}      color="green" />
              <MetricCard label="Cameras Offline" value={data.system.cameras_offline} icon={Camera}      color="yellow" />
              <MetricCard label="Cameras Error"   value={data.system.cameras_error}   icon={Camera}      color="red" />
              <MetricCard label="Frames Received" value={data.system.frames_received.toLocaleString()} icon={Cpu} color="blue" />
              <MetricCard label="Frames Dropped"  value={data.system.frames_dropped.toLocaleString()}  icon={Cpu} color={data.system.frames_dropped > 0 ? 'red' : 'gray'} />
              <MetricCard label="Avg Latency"     value={fmtMs(data.system.avg_latency_ms)} icon={Activity} color="purple" description="Frame processing latency" />
              <MetricCard
                label="DB Health"
                value={data.system.db_healthy ? 'OK' : 'Error'}
                icon={data.system.db_healthy ? CheckCircle2 : XCircle}
                color={data.system.db_healthy ? 'green' : 'red'}
              />
              <MetricCard
                label="Generated"
                value={new Date(data.generated_at).toLocaleTimeString()}
                color="gray"
                description={`Range: ${data.time_range}`}
              />
            </div>
          </section>

          {/* ─── AI Pipeline ─────────────────────────────────────────────── */}
          <section>
            <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Cpu className="w-4 h-4" /> AI Pipeline
            </h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <PerformanceChart
                title="Pipeline Throughput (Successful Count per Stage)"
                items={pipelineChartItems}
                valueFormatter={(v) => v.toLocaleString()}
              />
              <div className="grid grid-cols-2 gap-3">
                {data.pipeline.map((stage) => (
                  <div key={stage.stage_name} className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{stage.stage_name.replace(/_/g, ' ')}</p>
                    <div className="mt-1 grid grid-cols-3 gap-1 text-center">
                      <div>
                        <div className="text-base font-bold text-blue-700">{stage.input_count}</div>
                        <div className="text-[10px] text-gray-400">Input</div>
                      </div>
                      <div>
                        <div className="text-base font-bold text-green-700">{stage.successful_count}</div>
                        <div className="text-[10px] text-gray-400">Success</div>
                      </div>
                      <div>
                        <div className={`text-base font-bold ${stage.failed_count > 0 ? 'text-red-700' : 'text-gray-400'}`}>{stage.failed_count}</div>
                        <div className="text-[10px] text-gray-400">Failed</div>
                      </div>
                    </div>
                    {stage.avg_latency_ms !== null && (
                      <p className="text-[10px] text-gray-400 mt-1 text-center">Avg {fmtMs(stage.avg_latency_ms)}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* ─── Matching & Review ───────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <section>
              <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                <TrendingUp className="w-4 h-4" /> Matching Performance
              </h2>
              <div className="grid grid-cols-2 gap-3">
                <MetricCard label="Queries Processed"  value={data.matching.queries_processed.toLocaleString()} color="blue" />
                <MetricCard label="Possible Matches"   value={data.matching.possible_matches.toLocaleString()}   color="purple" />
                <MetricCard label="Top-1 Accuracy"     value={fmtPct(data.matching.top1_accuracy)}               color="green"  description="Rank-1 retrieval rate" />
                <MetricCard label="Top-5 Retrieval"    value={fmtPct(data.matching.top5_retrieval_rate)}         color="green"  description="Top-5 retrieval rate" />
                <MetricCard label="False Match Rate"   value={fmtPct(data.matching.fmr)}                         color={data.matching.fmr && data.matching.fmr > 0.1 ? 'red' : 'gray'} description="FMR — human review outcomes" />
                <MetricCard label="False Non-Match"    value={fmtPct(data.matching.fnmr)}                        color="gray"   description="FNMR" />
                <MetricCard label="Avg Search Latency" value={fmtMs(data.matching.avg_search_latency_ms)}        color="blue" />
                <MetricCard label="No Candidates"      value={data.matching.no_candidate_results.toLocaleString()} color="yellow" />
              </div>
            </section>

            <section>
              <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                <Users className="w-4 h-4" /> Human Review Workflow
              </h2>
              <p className="text-xs text-gray-400 mb-3 italic">
                Note: These metrics describe system workflow only and must not be used to evaluate individual reviewers.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <MetricCard label="Reviews Created"    value={data.reviews.reviews_created}    color="blue" />
                <MetricCard label="Reviews Completed"  value={data.reviews.reviews_completed}  color="green" />
                <MetricCard label="Pending Reviews"    value={data.reviews.pending_reviews}    color={data.reviews.pending_reviews > 10 ? 'yellow' : 'gray'} />
                <MetricCard label="Confirmed"          value={data.reviews.confirmed_for_action} color="green" description="Confirmed for action" />
                <MetricCard label="Rejected"           value={data.reviews.rejected}           color="red" />
                <MetricCard label="Need More Evidence" value={data.reviews.need_more_evidence} color="yellow" />
                <MetricCard label="Avg Review Time"    value={fmtSec(data.reviews.avg_review_time_seconds)} color="purple" />
              </div>
            </section>
          </div>

          {/* ─── Alerts & Evidence ───────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <section>
              <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                <Bell className="w-4 h-4" /> Alert Performance
              </h2>
              <div className="grid grid-cols-2 gap-3">
                <MetricCard label="Alerts Created"      value={data.alerts.alerts_created}      color="blue" />
                <MetricCard label="Acknowledged"        value={data.alerts.alerts_acknowledged} color="green" />
                <MetricCard label="In Progress"         value={data.alerts.alerts_in_progress}  color="yellow" />
                <MetricCard label="Resolved"            value={data.alerts.alerts_resolved}     color="green" />
                <MetricCard label="Failed"              value={data.alerts.alerts_failed}       color={data.alerts.alerts_failed > 0 ? 'red' : 'gray'} />
                <MetricCard label="Notif. Failures"     value={data.alerts.notification_failures} color={data.alerts.notification_failures > 0 ? 'red' : 'gray'} />
                <MetricCard label="Avg Ack Time"        value={fmtSec(data.alerts.avg_acknowledgment_time_seconds)} color="purple" />
                <MetricCard label="Avg Notif Latency"   value={fmtMs(data.alerts.avg_notification_latency_ms)} color="blue" />
              </div>
            </section>

            <section>
              <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                <FolderLock className="w-4 h-4" /> Evidence Management
              </h2>
              <div className="grid grid-cols-2 gap-3">
                <MetricCard label="Evidence Items"     value={data.evidence.evidence_created.toLocaleString()} color="blue" />
                <MetricCard label="Images"             value={data.evidence.images}            color="purple" />
                <MetricCard label="Videos"             value={data.evidence.videos}            color="purple" />
                <MetricCard label="Documents"          value={data.evidence.documents}         color="gray" />
                <MetricCard label="Integrity Checks"   value={data.evidence.integrity_checks}  color="green" />
                <MetricCard label="Integrity Failures" value={data.evidence.integrity_failures} color={data.evidence.integrity_failures > 0 ? 'red' : 'gray'} />
                <MetricCard label="Exports"            value={data.evidence.evidence_exports}  color="blue" />
                <MetricCard label="Storage Used"
                  value={(data.evidence.total_size_bytes / (1024 * 1024)).toFixed(1)}
                  suffix="MB"
                  color="gray"
                />
              </div>
            </section>
          </div>

          {/* Privacy disclaimer */}
          <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
            <p className="text-xs text-gray-500 text-center">
              All metrics are aggregated system statistics. No personal data, biometric data, or PII is included in this dashboard.
              Evaluation metrics are specific to the evaluated dataset and conditions and must not be automatically generalized.
            </p>
          </div>
        </>
      )}

      {/* Suppress unused variable warning for rejectionItems */}
      {rejectionItems.length > 0 && null}
    </div>
  );
}
