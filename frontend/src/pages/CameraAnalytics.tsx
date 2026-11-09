/**
 * CameraAnalytics – Module 11 per-camera analytics page.
 * 
 * Shows frame processing, detection, and quality stats per authorized camera.
 * Does not rank individuals or departments — technical data quality metrics only.
 */

import { useState, useEffect, useCallback } from 'react';
import { Camera, RefreshCw, TrendingUp, AlertTriangle } from 'lucide-react';
import MetricCard from '../components/MetricCard';
import PerformanceChart from '../components/PerformanceChart';
import { getCameraAnalytics, getFaceQualityBreakdown } from '../services/analyticsApi';
import type { CameraAnalyticsItem, FaceQualityBreakdown, TimeRange } from '../types/analytics';

const TIME_RANGES: { label: string; value: TimeRange }[] = [
  { label: 'Today', value: 'today' },
  { label: '7 Days', value: '7d' },
  { label: '30 Days', value: '30d' },
];

export default function CameraAnalytics() {
  const [timeRange, setTimeRange] = useState<TimeRange>('7d');
  const [cameras, setCameras] = useState<CameraAnalyticsItem[]>([]);
  const [quality, setQuality] = useState<FaceQualityBreakdown | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [cams, q] = await Promise.all([
        getCameraAnalytics(timeRange),
        getFaceQualityBreakdown(timeRange),
      ]);
      setCameras(cams);
      setQuality(q);
    } catch { /* silent */ }
    setLoading(false);
  }, [timeRange]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Summary metrics across all cameras
  const totalFrames = cameras.reduce((s, c) => s + c.frames_received, 0);
  const totalDetections = cameras.reduce((s, c) => s + c.detections, 0);
  const totalCandidates = cameras.reduce((s, c) => s + c.face_candidates, 0);
  const totalErrors = cameras.reduce((s, c) => s + c.error_count, 0);

  const detectionChartItems = cameras
    .sort((a, b) => b.detections - a.detections)
    .slice(0, 10)
    .map((c) => ({
      label: c.camera_name,
      value: c.detections,
      color: 'bg-blue-500',
    }));

  const latencyChartItems = cameras
    .filter((c) => c.avg_latency_ms !== null)
    .sort((a, b) => (b.avg_latency_ms ?? 0) - (a.avg_latency_ms ?? 0))
    .slice(0, 10)
    .map((c) => ({
      label: c.camera_name,
      value: c.avg_latency_ms ?? 0,
      color: (c.avg_latency_ms ?? 0) > 200 ? 'bg-red-400' : 'bg-green-500',
    }));

  const rejectionItems = quality
    ? Object.entries(quality.rejection_reasons)
        .sort(([, a], [, b]) => b - a)
        .map(([reason, count]) => ({
          label: reason.replace(/_/g, ' '),
          value: count,
          color: 'bg-orange-400',
        }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Camera className="w-6 h-6 text-blue-600" />
            Camera Analytics
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Per-camera processing and quality metrics.
            Technical data quality indicators — not a performance ranking of officers or departments.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-gray-100 rounded-lg p-0.5 gap-0.5">
            {TIME_RANGES.map((tr) => (
              <button
                key={tr.value}
                onClick={() => setTimeRange(tr.value)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                  timeRange === tr.value ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {tr.label}
              </button>
            ))}
          </div>
          <button onClick={fetchData} disabled={loading} className="p-2 text-gray-400 hover:text-gray-600 rounded-lg">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard label="Active Cameras"    value={cameras.length}               icon={Camera}      color="blue" />
        <MetricCard label="Total Frames"      value={totalFrames.toLocaleString()} icon={TrendingUp}  color="blue" />
        <MetricCard label="Total Detections"  value={totalDetections.toLocaleString()}  color="green" />
        <MetricCard label="Face Candidates"   value={totalCandidates.toLocaleString()} color="purple" />
        <MetricCard label="Error Events"      value={totalErrors} color={totalErrors > 0 ? 'red' : 'gray'} icon={AlertTriangle} />
        {quality && (
          <>
            <MetricCard label="Faces Received" value={quality.faces_received} color="blue" />
            <MetricCard label="Faces Passed"   value={quality.faces_passed}   color="green" />
            <MetricCard label="Avg Quality"
              value={quality.avg_quality_score !== null ? quality.avg_quality_score.toFixed(3) : '—'}
              color="purple"
              description="Mean quality score (0-1)"
            />
          </>
        )}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <PerformanceChart
          title="Detections per Camera (Top 10)"
          items={detectionChartItems}
          emptyMessage="No detection data."
        />
        <PerformanceChart
          title="Avg Processing Latency per Camera (ms)"
          items={latencyChartItems}
          valueFormatter={(v) => `${v.toFixed(1)} ms`}
          emptyMessage="No latency data."
        />
        <PerformanceChart
          title="Face Rejection Reasons"
          items={rejectionItems}
          emptyMessage="No rejection data."
        />
      </div>

      {/* Detailed camera table */}
      <section>
        <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">Camera Detail</h2>
        {cameras.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400 text-sm">
            {loading ? 'Loading camera data…' : 'No cameras found for the selected period.'}
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    {['Camera', 'Frames', 'Processed', 'Dropped', 'Drop %', 'Detections', 'Face Candidates', 'Avg Latency', 'Errors'].map((h) => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {cameras.map((cam) => {
                    const dropPct = cam.frames_received > 0
                      ? ((cam.frames_dropped / cam.frames_received) * 100).toFixed(1)
                      : '0.0';
                    return (
                      <tr key={cam.camera_id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3">
                          <p className="font-medium text-gray-800">{cam.camera_name}</p>
                          <p className="text-xs text-gray-400">ID: {cam.camera_id}</p>
                        </td>
                        <td className="px-4 py-3 text-gray-700">{cam.frames_received.toLocaleString()}</td>
                        <td className="px-4 py-3 text-green-700">{cam.frames_processed.toLocaleString()}</td>
                        <td className="px-4 py-3">
                          <span className={parseFloat(dropPct) > 5 ? 'text-red-600 font-medium' : 'text-gray-400'}>
                            {cam.frames_dropped.toLocaleString()}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={parseFloat(dropPct) > 5 ? 'text-red-600 font-semibold' : 'text-gray-400'}>
                            {dropPct}%
                          </span>
                        </td>
                        <td className="px-4 py-3 text-blue-700">{cam.detections.toLocaleString()}</td>
                        <td className="px-4 py-3 text-purple-700">{cam.face_candidates.toLocaleString()}</td>
                        <td className="px-4 py-3 text-gray-600">
                          {cam.avg_latency_ms !== null ? `${cam.avg_latency_ms.toFixed(1)} ms` : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <span className={cam.error_count > 0 ? 'text-red-600 font-semibold' : 'text-gray-300'}>
                            {cam.error_count}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* Note */}
      <div className="p-3 bg-blue-50 border border-blue-100 rounded-lg">
        <p className="text-xs text-blue-700">
          <strong>Note:</strong> Camera analytics identify technical data quality issues such as frame drops, 
          high latency, or poor face quality. These metrics should not be interpreted as a judgment about 
          personnel, departments, or the individuals captured in footage.
        </p>
      </div>
    </div>
  );
}
