import React from 'react';
import { Clock, CheckCircle2, Bell, AlertTriangle, Eye, ShieldCheck, ArrowRightCircle } from 'lucide-react';
import type { AlertTimeline as AlertTimelineType } from '../types/alert';
import { format, parseISO } from 'date-fns';

interface AlertTimelineProps {
  timeline: AlertTimelineType[];
}

export const AlertTimeline: React.FC<AlertTimelineProps> = ({ timeline }) => {
  const getEventIcon = (type: string) => {
    switch (type) {
      case 'POSSIBLE_MATCH_REVIEWED':
        return <ShieldCheck className="w-4 h-4 text-emerald-600" />;
      case 'ALERT_CREATED':
        return <Bell className="w-4 h-4 text-blue-600" />;
      case 'ORIGINATING_DEPARTMENT_NOTIFIED':
      case 'NEAREST_DEPARTMENT_NOTIFIED':
        return <ArrowRightCircle className="w-4 h-4 text-indigo-600" />;
      case 'ALERT_ACKNOWLEDGED':
        return <CheckCircle2 className="w-4 h-4 text-amber-600" />;
      case 'OBSERVATION_UPDATED':
        return <Eye className="w-4 h-4 text-purple-600" />;
      case 'ALERT_ESCALATED':
        return <AlertTriangle className="w-4 h-4 text-red-600" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm space-y-4">
      <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider flex items-center gap-2 border-b border-gray-100 pb-2">
        <Clock className="w-4 h-4 text-blue-600" />
        Alert Milestones &amp; Audit Timeline
      </h3>

      <div className="relative pl-6 space-y-6 before:content-[''] before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-gray-200">
        {timeline.map((item, index) => {
          const formattedDate = item.timestamp
            ? format(parseISO(item.timestamp), 'yyyy-MM-dd HH:mm:ss')
            : 'Pending';

          return (
            <div key={item.id || index} className="relative group">
              {/* Circle Marker */}
              <div className="absolute -left-6 top-0.5 w-4 h-4 rounded-full bg-white border-2 border-gray-300 flex items-center justify-center group-hover:border-blue-500 transition-colors">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
              </div>

              <div className="bg-gray-50/70 border border-gray-100 rounded-md p-3 space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-gray-800 flex items-center gap-1.5">
                    {getEventIcon(item.event_type)}
                    {item.event_type.replace(/_/g, ' ')}
                  </span>
                  <span className="text-gray-400 font-mono text-[11px]">{formattedDate} UTC</span>
                </div>
                <p className="text-xs text-gray-600 leading-relaxed">{item.description}</p>
              </div>
            </div>
          );
        })}

        {timeline.length === 0 && (
          <div className="text-xs text-gray-400 py-3 text-center">No timeline milestones recorded yet.</div>
        )}
      </div>
    </div>
  );
};
