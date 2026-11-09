import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Camera, MapPin, Building2, Clock, Eye } from 'lucide-react';
import type { AlertItem } from '../types/alert';
import { AlertPriorityBadge, AlertStatusBadge } from './AlertStatus';
import { formatDistanceToNow, parseISO } from 'date-fns';

interface AlertCardProps {
  alert: AlertItem;
}

export const AlertCard: React.FC<AlertCardProps> = ({ alert }) => {
  const navigate = useNavigate();

  const formattedTime = alert.created_at
    ? formatDistanceToNow(parseISO(alert.created_at), { addSuffix: true })
    : 'Unknown time';

  return (
    <div
      onClick={() => navigate(`/alerts/${alert.id}`)}
      className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm hover:shadow-md transition-all cursor-pointer relative hover:border-blue-400 group"
    >
      {/* Top Banner: Alert Number + Badges */}
      <div className="flex items-center justify-between gap-2 border-b border-gray-100 pb-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
            {alert.alert_number}
          </span>
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded ${
              alert.category === 'WANTED'
                ? 'bg-rose-100 text-rose-800'
                : 'bg-amber-100 text-amber-800'
            }`}
          >
            {alert.category}
          </span>
          {alert.observation_count > 1 && (
            <span className="text-[11px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 px-1.5 py-0.5 rounded-full flex items-center gap-1">
              <Eye className="w-3 h-3" /> {alert.observation_count} Observations
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <AlertPriorityBadge priority={alert.priority} size="sm" />
          <AlertStatusBadge status={alert.status} size="sm" />
        </div>
      </div>

      {/* Main Case Info */}
      <div className="mb-3">
        <div className="flex items-baseline justify-between">
          <h3 className="text-base font-bold text-gray-900 group-hover:text-blue-600 transition-colors">
            Case: {alert.case_number}
          </h3>
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" /> {formattedTime}
          </span>
        </div>
      </div>

      {/* Context Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-600 bg-gray-50 p-3 rounded-md mb-3">
        <div className="flex items-center gap-2">
          <Camera className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
          <span className="truncate">
            Camera: <strong className="text-gray-700">{alert.detected_camera_code || 'CAM-CCTV'}</strong>
          </span>
        </div>

        <div className="flex items-center gap-2">
          <MapPin className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
          <span className="truncate">
            Location: <strong className="text-gray-700">{alert.detected_location || 'Authorized Zone'}</strong>
          </span>
        </div>

        <div className="flex items-center gap-2 col-span-1 md:col-span-2">
          <Building2 className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
          <span className="truncate">
            Case Dept: <strong className="text-gray-800">{alert.originating_department_name || `Dept #${alert.originating_department_id}`}</strong>
            {alert.nearest_department_name && alert.nearest_department_id !== alert.originating_department_id && (
              <> &bull; Nearest Dept: <strong className="text-gray-800">{alert.nearest_department_name}</strong> {alert.distance_km != null && `(${alert.distance_km} km)`}</>
            )}
          </span>
        </div>
      </div>

      {/* Routing Reason Snippet */}
      {alert.routing_reason && (
        <p className="text-[11px] text-gray-500 italic truncate border-t border-gray-100 pt-2">
          {alert.routing_reason}
        </p>
      )}
    </div>
  );
};
