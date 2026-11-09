import React from 'react';
import { Camera, User, AlertTriangle } from 'lucide-react';
import type { ReviewEventDetail } from '../types/review';
import { StatusBadge } from './StatusBadge';

interface ComparisonViewerProps {
  event: ReviewEventDetail;
}

export const ComparisonViewer: React.FC<ComparisonViewerProps> = ({ event }) => {
  return (
    <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden flex flex-col h-full">
      <div className="bg-blue-900 px-4 py-2 flex items-center justify-between text-white">
        <span className="font-semibold text-sm">Side-by-Side Comparison Analysis</span>
        <span className="text-xs opacity-80 font-mono">EVT: {event.match_event_id.substring(0, 8)}</span>
      </div>
      
      <div className="flex-1 flex flex-col sm:flex-row relative">
        {/* Left: CCTV */}
        <div className="flex-1 p-4 flex flex-col">
          <div className="mb-2 flex justify-between items-center text-sm">
            <span className="font-semibold text-gray-700 flex items-center gap-1"><Camera className="w-4 h-4"/> CCTV Observation</span>
            <span className="text-gray-500 font-mono">{new Date(event.created_at).toLocaleTimeString()}</span>
          </div>
          
          <div className="bg-gray-900 rounded flex-1 min-h-[300px] flex flex-col items-center justify-center relative overflow-hidden group border border-gray-300">
            {/* Guide lines - conceptual */}
            <div className="absolute inset-0 border-[0.5px] border-white border-opacity-10 grid grid-cols-3 grid-rows-3 pointer-events-none">
              <div className="border-r border-b border-white border-opacity-10"></div>
              <div className="border-r border-b border-white border-opacity-10"></div>
              <div className="border-b border-white border-opacity-10"></div>
              <div className="border-r border-b border-white border-opacity-10"></div>
              <div className="border-r border-b border-white border-opacity-10"></div>
              <div className="border-b border-white border-opacity-10"></div>
              <div className="border-r border-white border-opacity-10"></div>
              <div className="border-r border-white border-opacity-10"></div>
              <div></div>
            </div>
            
            <Camera className="w-10 h-10 text-gray-600 mb-2" />
            <span className="text-gray-500 text-sm">Observation Frame</span>
          </div>
          
          <div className="mt-2 text-xs text-gray-500 flex justify-between">
            <span>CAM: {event.camera_location || event.camera_id}</span>
            <span>Q: {event.face_quality_label}</span>
          </div>
        </div>
        
        {/* VS Divider */}
        <div className="sm:absolute sm:left-1/2 sm:top-1/2 sm:-translate-x-1/2 sm:-translate-y-1/2 z-10 flex items-center justify-center py-2 sm:py-0">
          <div className="bg-white rounded-full p-2 shadow-lg border border-gray-200">
            <div className="bg-gray-100 rounded-full w-8 h-8 flex items-center justify-center font-bold text-gray-500 text-xs">
              VS
            </div>
          </div>
        </div>
        
        {/* Right: Reference */}
        <div className="flex-1 p-4 flex flex-col bg-gray-50 border-t sm:border-t-0 sm:border-l border-gray-200">
          <div className="mb-2 flex justify-between items-center text-sm">
            <span className="font-semibold text-gray-700 flex items-center gap-1"><User className="w-4 h-4"/> Reference</span>
            <StatusBadge status={event.category} type="category" />
          </div>
          
          <div className="bg-white rounded flex-1 min-h-[300px] flex flex-col items-center justify-center relative overflow-hidden border border-gray-300">
             <div className="absolute inset-0 border-[0.5px] border-black border-opacity-5 grid grid-cols-3 grid-rows-3 pointer-events-none">
              <div className="border-r border-b border-black border-opacity-5"></div>
              <div className="border-r border-b border-black border-opacity-5"></div>
              <div className="border-b border-black border-opacity-5"></div>
              <div className="border-r border-b border-black border-opacity-5"></div>
              <div className="border-r border-b border-black border-opacity-5"></div>
              <div className="border-b border-black border-opacity-5"></div>
              <div className="border-r border-black border-opacity-5"></div>
              <div className="border-r border-black border-opacity-5"></div>
              <div></div>
            </div>
            
            <User className="w-10 h-10 text-gray-300 mb-2" />
            <span className="text-gray-400 text-sm">Reference Image</span>
          </div>
          
          <div className="mt-2 text-xs text-gray-500 flex justify-between">
            <span className="font-semibold text-blue-700">{event.case_number}</span>
          </div>
        </div>
      </div>
      
      <div className="bg-amber-50 border-t border-amber-200 p-2 text-center text-xs text-amber-800 flex items-center justify-center gap-2">
        <AlertTriangle className="w-3 h-3" />
        Raw unmodified images shown. Do not rely solely on visual comparison for identification.
      </div>
    </div>
  );
};
