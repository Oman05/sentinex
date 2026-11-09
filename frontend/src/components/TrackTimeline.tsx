import React from 'react';
import { format } from 'date-fns';
import { Activity, Star } from 'lucide-react';
import type { TrackHistory } from '../types/review';

interface TrackTimelineProps {
  track: TrackHistory | null;
  isLoading?: boolean;
}

export const TrackTimeline: React.FC<TrackTimelineProps> = ({ track, isLoading }) => {
  if (isLoading) {
    return <div className="p-8 text-center text-gray-500 animate-pulse">Loading track history...</div>;
  }

  if (!track || !track.observations || track.observations.length === 0) {
    return (
      <div className="p-8 text-center border rounded bg-gray-50">
        <Activity className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        <p className="text-gray-600">No track history available for this event.</p>
        <p className="text-sm text-gray-500 mt-1">This observation was recorded as an isolated detection.</p>
      </div>
    );
  }

  // Sort observations by timestamp ascending
  const sortedObs = [...track.observations].sort((a, b) => 
    new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200">
      <div className="border-b border-gray-200 px-4 py-3 bg-gray-50 rounded-t-lg">
        <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-600" />
          Track History <span className="font-mono text-xs text-gray-500 ml-2">ID: {track.track_id}</span>
        </h3>
      </div>
      
      <div className="p-4 overflow-x-auto">
        <div className="relative pt-8 pb-4 min-w-[600px]">
          {/* Timeline connecting line */}
          <div className="absolute top-12 left-0 right-0 h-0.5 bg-blue-100 z-0"></div>
          
          <div className="flex justify-between relative z-10">
            {sortedObs.map((obs) => {
              const isBest = obs.observation_id === track.best_quality_observation_id;
              
              return (
                <div key={obs.observation_id} className="flex flex-col items-center group cursor-pointer" style={{ width: `${100 / sortedObs.length}%` }}>
                  <div className={`text-xs text-gray-500 mb-2 whitespace-nowrap ${isBest ? 'font-bold text-blue-700' : ''}`}>
                    {format(new Date(obs.timestamp), 'HH:mm:ss')}
                  </div>
                  
                  <div className={`w-4 h-4 rounded-full border-2 bg-white flex items-center justify-center
                    ${isBest ? 'border-blue-500 w-6 h-6 ring-4 ring-blue-100' : 'border-gray-300 group-hover:border-blue-400'}
                  `}>
                    {isBest && <Star className="w-3 h-3 text-blue-500" />}
                  </div>
                  
                  <div className="mt-3 text-center">
                    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-medium border
                      ${isBest ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-gray-50 text-gray-600 border-gray-200'}
                    `}>
                      {obs.quality_label}
                    </span>
                    <div className="text-[10px] text-gray-400 mt-1">
                      Score: {obs.quality_score.toFixed(2)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
