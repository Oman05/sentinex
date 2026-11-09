import React from 'react';
import { Brain, Target, Shield, Info } from 'lucide-react';
import { SIMILARITY_DISCLAIMER } from "../types/review";
import type { ReviewEventDetail } from '../types/review';

interface AIAnalysisPanelProps {
  event: ReviewEventDetail;
}

export const AIAnalysisPanel: React.FC<AIAnalysisPanelProps> = ({ event }) => {
  return (
    <div className="bg-white rounded-lg shadow border border-gray-200">
      <div className="border-b border-gray-200 px-4 py-3 flex items-center justify-between bg-gray-50 rounded-t-lg">
        <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
          <Brain className="w-4 h-4 text-blue-600" />
          Algorithmic Analysis
        </h3>
        <span className="text-xs font-semibold text-amber-700 bg-amber-100 px-2 py-1 rounded-full border border-amber-200">
          PENDING HUMAN REVIEW
        </span>
      </div>

      <div className="p-4">
        <div className="bg-blue-50 border border-blue-200 rounded-md p-3 flex gap-3 mb-6">
          <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-800">
            <span className="font-semibold block mb-1">AI ANALYSIS NOTE:</span>
            The AI system generates candidate match signals for authorized human review. These signals require examination by an authorized officer before any operational decision.
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-4">
            <div>
              <div className="text-sm text-gray-500 mb-1 flex items-center gap-1">
                <Target className="w-4 h-4" /> Similarity Signal Score
              </div>
              <div className="text-2xl font-bold text-gray-900 flex items-end gap-2">
                {event.similarity_score?.toFixed(4) || 'N/A'}
                <span className="text-xs font-normal text-gray-500 mb-1" title={SIMILARITY_DISCLAIMER}>
                  (Not a percentage identity)
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1 italic">{SIMILARITY_DISCLAIMER}</p>
            </div>

            <div>
              <div className="text-sm text-gray-500 mb-1">Candidate Rank</div>
              <div className="text-xl font-semibold text-gray-800">
                #{event.rank || '?'}
              </div>
            </div>
            
            <div>
              <div className="text-sm text-gray-500 mb-1">Detection Quality Score</div>
              <div className="text-lg font-medium text-gray-800">
                {event.detection_quality_score?.toFixed(2) || 'N/A'}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <div className="text-sm text-gray-500 mb-1">Face Quality Label</div>
              <div className="text-lg font-medium text-gray-800">
                {event.face_quality_label || 'Unknown'}
              </div>
            </div>

            <div>
              <div className="text-sm text-gray-500 mb-1">Observation Count</div>
              <div className="text-lg font-medium text-gray-800">
                {event.observation_count || 1} frames analyzed
              </div>
            </div>

            <div>
              <div className="text-sm text-gray-500 mb-1 flex items-center gap-1">
                <Shield className="w-4 h-4" /> System Model
              </div>
              <div className="text-sm text-gray-800">
                {event.model_name || 'sentinex-core'} <span className="text-gray-500 text-xs">v{event.model_version || '1.0'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
