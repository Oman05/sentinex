import React, { useState } from 'react';
import { AlertOctagon, CheckCircle, HelpCircle, AlertTriangle } from 'lucide-react';
import type { ReviewDecision, EvidenceRequestType } from '../types/review';

interface ReviewDecisionPanelProps {
  status: string;
  onSubmitDecision: (decision: ReviewDecision, notes: string) => void;
  onRequestEvidence: (type: EvidenceRequestType, notes: string) => void;
}

export const ReviewDecisionPanel: React.FC<ReviewDecisionPanelProps> = ({ 
  status, 
  onSubmitDecision, 
  onRequestEvidence 
}) => {
  const isTerminal = status === 'CONFIRMED_FOR_ACTION' || status === 'REJECTED';
  const [activeAction, setActiveAction] = useState<ReviewDecision | 'EVIDENCE' | null>(null);
  const [notes, setNotes] = useState('');
  const [evidenceType, setEvidenceType] = useState<EvidenceRequestType>('ADDITIONAL_OBSERVATIONS');

  const handleSubmit = () => {
    if (activeAction === 'EVIDENCE') {
      onRequestEvidence(evidenceType, notes);
    } else if (activeAction) {
      onSubmitDecision(activeAction, notes);
    }
    setActiveAction(null);
    setNotes('');
  };

  if (isTerminal) {
    return (
      <div className="bg-gray-50 p-6 rounded-lg border border-gray-200 text-center">
        <p className="text-gray-600 mb-2">Review is complete</p>
        <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full font-bold ${
          status === 'CONFIRMED_FOR_ACTION' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
        }`}>
          {status === 'CONFIRMED_FOR_ACTION' ? <CheckCircle className="w-5 h-5" /> : <AlertOctagon className="w-5 h-5" />}
          {status.replace(/_/g, ' ')}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200 p-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 border-b pb-2">Record Review Decision</h3>
      
      {!activeAction ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <button
            onClick={() => setActiveAction('CONFIRM_FOR_ACTION')}
            className="flex flex-col items-center justify-center p-4 rounded border-2 border-green-200 bg-green-50 hover:bg-green-100 hover:border-green-300 transition-colors"
          >
            <CheckCircle className="w-8 h-8 text-green-600 mb-2" />
            <span className="font-bold text-green-800">CONFIRM FOR ACTION</span>
          </button>
          
          <button
            onClick={() => setActiveAction('REJECTED')}
            className="flex flex-col items-center justify-center p-4 rounded border-2 border-red-200 bg-red-50 hover:bg-red-100 hover:border-red-300 transition-colors"
          >
            <AlertOctagon className="w-8 h-8 text-red-600 mb-2" />
            <span className="font-bold text-red-800">REJECT MATCH</span>
          </button>
          
          <button
            onClick={() => setActiveAction('EVIDENCE')}
            className="flex flex-col items-center justify-center p-4 rounded border-2 border-amber-200 bg-amber-50 hover:bg-amber-100 hover:border-amber-300 transition-colors"
          >
            <HelpCircle className="w-8 h-8 text-amber-600 mb-2" />
            <span className="font-bold text-amber-800">NEED MORE EVIDENCE</span>
          </button>
        </div>
      ) : (
        <div className="space-y-4 animate-in fade-in slide-in-from-top-4 duration-200">
          <div className={`p-3 rounded border flex items-start gap-3 ${
            activeAction === 'CONFIRM_FOR_ACTION' ? 'bg-green-50 border-green-200 text-green-900' :
            activeAction === 'REJECTED' ? 'bg-red-50 border-red-200 text-red-900' :
            'bg-amber-50 border-amber-200 text-amber-900'
          }`}>
            <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">
                You selected: {activeAction === 'EVIDENCE' ? 'NEED MORE EVIDENCE' : activeAction.replace(/_/g, ' ')}
              </p>
              {activeAction === 'CONFIRM_FOR_ACTION' && (
                <p className="text-sm mt-1">
                  CONFIRM FOR ACTION means you authorize proceeding to the next investigative step. It does NOT mean the AI has confirmed this person's identity.
                </p>
              )}
            </div>
          </div>

          {activeAction === 'EVIDENCE' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Request Type</label>
              <select
                value={evidenceType}
                onChange={(e) => setEvidenceType(e.target.value as EvidenceRequestType)}
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
              >
                <option value="ADDITIONAL_OBSERVATIONS">Additional Track Observations</option>
                <option value="ADDITIONAL_CAMERA_FOOTAGE">Surrounding Camera Footage</option>
                <option value="DIFFERENT_TIME_INTERVAL">Extended Time Interval</option>
                <option value="ADDITIONAL_REFERENCE_IMAGE">Better Reference Image Needed</option>
                <option value="REASSIGN_REVIEWER">Reassign to Specialist</option>
              </select>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Analysis Notes {activeAction === 'REJECTED' && <span className="text-red-500">*</span>}
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border min-h-[100px]"
              placeholder="Enter your rationale..."
              required={activeAction === 'REJECTED'}
            />
          </div>

          <div className="bg-gray-50 p-3 rounded text-sm text-gray-600 flex gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0 text-gray-400" />
            <p>You are about to submit a review decision. This action will be recorded in the audit log and cannot be silently modified.</p>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => { setActiveAction(null); setNotes(''); }}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={activeAction === 'REJECTED' && !notes.trim()}
              className={`px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white ${
                activeAction === 'CONFIRM_FOR_ACTION' ? 'bg-green-600 hover:bg-green-700' :
                activeAction === 'REJECTED' ? 'bg-red-600 hover:bg-red-700' :
                'bg-amber-600 hover:bg-amber-700'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              Submit to Audit Log
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
