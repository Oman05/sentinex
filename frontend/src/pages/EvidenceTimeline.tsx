import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import type { EvidenceTimelineResponse } from '../types/evidence';
import { getEvidenceTimeline } from '../services/evidenceApi';
import { EvidenceTimeline as EvidenceTimelineComponent } from '../components/EvidenceTimeline';

export default function EvidenceTimelinePage() {
  const { evidenceId } = useParams<{ evidenceId: string }>();
  const navigate = useNavigate();
  const [timeline, setTimeline] = useState<EvidenceTimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!evidenceId) return;
    setLoading(true);
    getEvidenceTimeline(evidenceId)
      .then((data) => setTimeline(data))
      .catch((err) => setError(err.response?.data?.detail || 'Failed to load timeline'))
      .finally(() => setLoading(false));
  }, [evidenceId]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(evidenceId ? `/evidence/${evidenceId}` : '/evidence')}
            className="p-2 bg-white border border-gray-200 rounded-lg text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900 font-mono">
              Timeline: {evidenceId || 'Evidence Item'}
            </h1>
            <p className="text-xs text-gray-500 mt-0.5">
              Chronological immutable audit sequence for item lifecycle events
            </p>
          </div>
        </div>

        <button
          onClick={() => navigate(evidenceId ? `/evidence/${evidenceId}` : '/evidence')}
          className="px-3 py-1.5 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700 transition-colors"
        >
          View Evidence Asset &rarr;
        </button>
      </div>

      {error ? (
        <div className="p-8 bg-white border border-red-200 rounded-xl text-center text-xs text-red-700">
          {error}
        </div>
      ) : (
        <EvidenceTimelineComponent
          entries={timeline?.entries || []}
          evidenceId={evidenceId || ''}
          caseNumber={timeline?.case_number}
          isLoading={loading}
        />
      )}
    </div>
  );
}
