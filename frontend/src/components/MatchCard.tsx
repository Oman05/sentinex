import React from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { Camera, Clock, User, AlertTriangle, ChevronRight } from 'lucide-react';
import { SIMILARITY_DISCLAIMER } from "../types/review";
import type { ReviewEventSummary } from '../types/review';
import { StatusBadge } from './StatusBadge';

interface MatchCardProps {
  event: ReviewEventSummary;
}

export const MatchCard: React.FC<MatchCardProps> = ({ event }) => {
  const navigate = useNavigate();

  return (
    <div 
      className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => navigate(`/review/${event.id}`)}
    >
      <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-600" />
        <span className="text-xs font-bold text-amber-800 tracking-wide">
          POSSIBLE MATCH — HUMAN REVIEW REQUIRED
        </span>
      </div>
      
      <div className="p-4">
        <div className="flex justify-between items-start mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg font-bold text-gray-900">{event.case_number}</span>
              <StatusBadge status={event.category} type="category" />
            </div>
            {event.priority && (
              <StatusBadge status={event.priority} type="priority" />
            )}
          </div>
          <StatusBadge status={event.status} />
        </div>

        <div className="grid grid-cols-2 gap-y-3 gap-x-4 text-sm mb-4">
          <div className="flex items-start gap-2 text-gray-600">
            <Camera className="w-4 h-4 mt-0.5 text-gray-400" />
            <div>
              <p className="font-medium text-gray-900">Location</p>
              <p>{event.camera_location || 'Unknown'}</p>
            </div>
          </div>
          
          <div className="flex items-start gap-2 text-gray-600">
            <Clock className="w-4 h-4 mt-0.5 text-gray-400" />
            <div>
              <p className="font-medium text-gray-900">Detection Time</p>
              <p>{format(new Date(event.created_at), 'PP p')}</p>
            </div>
          </div>
          
          <div className="flex items-start gap-2 text-gray-600">
            <User className="w-4 h-4 mt-0.5 text-gray-400" />
            <div>
              <p className="font-medium text-gray-900">Assigned To</p>
              <p>{event.assigned_to ? `Officer ${event.assigned_to}` : 'Unassigned'}</p>
            </div>
          </div>
          
          <div className="flex flex-col">
            <p className="font-medium text-gray-900">Face Quality</p>
            <p className="text-gray-600">{event.face_quality_label || 'Unknown'}</p>
          </div>
        </div>

        <div className="bg-gray-50 rounded p-3 border border-gray-100 flex justify-between items-center">
          <div>
            <p className="text-xs text-gray-500 mb-1">AI Analysis</p>
            <div className="flex items-center gap-4">
              <div>
                <span className="text-xs text-gray-500 mr-1">Rank:</span>
                <span className="font-semibold text-gray-900">#{event.rank || '?'}</span>
              </div>
              <div title={SIMILARITY_DISCLAIMER} className="cursor-help border-b border-dashed border-gray-400">
                <span className="text-xs text-gray-500 mr-1">Signal Score:</span>
                <span className="font-semibold text-gray-900">{event.similarity_score?.toFixed(2) || 'N/A'}</span>
              </div>
            </div>
          </div>
          <ChevronRight className="w-5 h-5 text-gray-400" />
        </div>
      </div>
    </div>
  );
};
