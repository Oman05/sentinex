import { useEffect, useState } from "react";
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Camera,
  MapPin,
  Clock,
  ShieldCheck,
  ExternalLink,
  Eye,
  Loader2,
  AlertTriangle,
  FileText,
} from 'lucide-react';
import type { AlertDetail } from '../types/alert';
import { getAlertDetail } from '../services/alertApi';
import { AlertPriorityBadge, AlertStatusBadge } from '../components/AlertStatus';
import { RecipientPanel } from '../components/RecipientPanel';
import { AcknowledgmentPanel } from '../components/AcknowledgmentPanel';
import { AlertTimeline } from '../components/AlertTimeline';
import { format, parseISO } from 'date-fns';

export default function AlertDetails() {
  const { alertId } = useParams<{ alertId: string }>();
  const navigate = useNavigate();
  const [alert, setAlert] = useState<AlertDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDetail = async () => {
    if (!alertId) return;
    try {
      setLoading(true);
      setError(null);
      const res = await getAlertDetail(Number(alertId));
      setAlert(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to fetch alert details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [alertId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-gray-400">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-2" />
        <span className="text-xs">Loading operational alert details...</span>
      </div>
    );
  }

  if (error || !alert) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 p-6 rounded-lg text-center space-y-3">
        <AlertTriangle className="w-8 h-8 text-red-500 mx-auto" />
        <h3 className="text-sm font-bold">Error Accessing Alert</h3>
        <p className="text-xs text-red-600">{error || 'Alert not found'}</p>
        <button
          onClick={() => navigate('/alerts')}
          className="bg-white border border-gray-300 text-gray-700 text-xs px-3 py-1.5 rounded-md hover:bg-gray-50"
        >
          Back to Alert Center
        </button>
      </div>
    );
  }

  const detectionTime = alert.created_at
    ? format(parseISO(alert.created_at), 'yyyy-MM-dd HH:mm:ss')
    : 'Unknown';

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Navigation & Header */}
      <div>
        <button
          onClick={() => navigate('/alerts')}
          className="text-xs font-semibold text-gray-500 hover:text-blue-600 flex items-center gap-1 mb-2 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Alert Center
        </button>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-sm font-bold text-gray-600 bg-gray-100 px-2 py-0.5 rounded">
                {alert.alert_number}
              </span>
              <span
                className={`text-xs font-bold px-2 py-0.5 rounded ${
                  alert.category === 'WANTED'
                    ? 'bg-rose-100 text-rose-800'
                    : 'bg-amber-100 text-amber-800'
                }`}
              >
                {alert.category}
              </span>
              {alert.observation_count > 1 && (
                <span className="text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.5 rounded-full flex items-center gap-1">
                  <Eye className="w-3 h-3" /> {alert.observation_count} Observations
                </span>
              )}
            </div>
            <h1 className="text-xl font-black text-gray-900 tracking-tight">
              Operational Alert: Case {alert.case_number}
            </h1>
            {alert.case_title && <p className="text-xs text-gray-500">{alert.case_title}</p>}
          </div>

          <div className="flex items-center gap-3">
            <AlertPriorityBadge priority={alert.priority} />
            <AlertStatusBadge status={alert.status} />
          </div>
        </div>
      </div>

      {/* AI Safety Invariant Banner */}
      <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-lg shadow-sm">
        <div className="flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="text-xs font-bold text-amber-900 uppercase tracking-wider">
              AI Safety Invariant — Human Verification Gated
            </h4>
            <p className="text-xs text-amber-800 leading-relaxed">
              {alert.similarity_disclaimer}
            </p>
            {alert.similarity_score != null && (
              <div className="text-[11px] text-amber-700 font-mono">
                Algorithmic Similarity Signal: <strong>{(alert.similarity_score * 100).toFixed(1)}%</strong> (Reference Candidate Metric)
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Grid: Context & Action Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Details & Recipients (2 Cols) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Detection & Case Metadata */}
          <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider flex items-center gap-2 border-b border-gray-100 pb-2">
              <Camera className="w-4 h-4 text-blue-600" />
              Detection &amp; Operational Context
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="space-y-1 bg-gray-50 p-3 rounded border border-gray-100">
                <span className="text-gray-400 font-medium block">Detected Camera</span>
                <span className="font-semibold text-gray-800 text-sm">
                  {alert.detected_camera_code || 'CAM-CCTV-001'}
                </span>
              </div>

              <div className="space-y-1 bg-gray-50 p-3 rounded border border-gray-100">
                <span className="text-gray-400 font-medium block">Location Description</span>
                <span className="font-semibold text-gray-800 text-sm flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-red-500" />
                  {alert.detected_location || 'Authorized CCTV Zone'}
                </span>
              </div>

              <div className="space-y-1 bg-gray-50 p-3 rounded border border-gray-100">
                <span className="text-gray-400 font-medium block">Initial Detection Timestamp</span>
                <span className="font-semibold text-gray-800 font-mono flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-blue-500" />
                  {detectionTime} UTC
                </span>
              </div>

              <div className="space-y-1 bg-gray-50 p-3 rounded border border-gray-100">
                <span className="text-gray-400 font-medium block">Module 8 Review Event Link</span>
                <button
                  onClick={() => navigate(`/review/${alert.review_event_id}`)}
                  className="font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1 underline"
                >
                  <FileText className="w-3.5 h-3.5" /> View Human Review Event #{alert.review_event_id}
                  <ExternalLink className="w-3 h-3 ml-0.5" />
                </button>
              </div>
            </div>

            {/* Examiner Decision Notes if present */}
            {alert.decision_notes && (
              <div className="border border-gray-200 rounded-md p-3 bg-gray-50 text-xs space-y-1">
                <span className="font-bold text-gray-700 block">Authorized Examiner Confirmation Notes:</span>
                <p className="text-gray-600 italic">"{alert.decision_notes}"</p>
              </div>
            )}
          </div>

          {/* Department Routing Panel */}
          <RecipientPanel alert={alert} />

          {/* Timeline Milestones */}
          <AlertTimeline timeline={alert.timeline} />
        </div>

        {/* Right Column: Actions & Quick Status */}
        <div className="space-y-6">
          <AcknowledgmentPanel alert={alert} onAlertUpdated={setAlert} />

          {/* Quick Case Card */}
          <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm space-y-3">
            <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider border-b border-gray-100 pb-2">
              Case Summary
            </h3>
            <div className="text-xs space-y-2">
              <div>
                <span className="text-gray-400 block">Subject Identifier:</span>
                <strong className="text-gray-800">{alert.person_identifier || 'Unknown'}</strong>
              </div>
              <div>
                <span className="text-gray-400 block">Case Priority:</span>
                <span className="text-gray-800 font-medium">{alert.case_priority || alert.priority}</span>
              </div>
              <div>
                <span className="text-gray-400 block">Originating Department:</span>
                <span className="text-gray-800 font-medium">{alert.originating_department_name || `Dept #${alert.originating_department_id}`}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
