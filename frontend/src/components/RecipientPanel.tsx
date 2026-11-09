import React from 'react';
import { Building2, Navigation, Mail, CheckCircle2 } from 'lucide-react';
import type { AlertDetail } from '../types/alert';
import { AlertStatusBadge } from './AlertStatus';

interface RecipientPanelProps {
  alert: AlertDetail;
}

export const RecipientPanel: React.FC<RecipientPanelProps> = ({ alert }) => {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm space-y-4">
      <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider flex items-center gap-2 border-b border-gray-100 pb-2">
        <Building2 className="w-4 h-4 text-blue-600" />
        Department Routing &amp; Notification Destinations
      </h3>

      {/* Routing Explanation Box */}
      {alert.routing_reason && (
        <div className="bg-blue-50/70 border border-blue-100 p-3 rounded-md text-xs text-blue-900 space-y-1">
          <div className="font-semibold flex items-center gap-1.5 text-blue-700">
            <Navigation className="w-3.5 h-3.5" /> Geospatial &amp; Jurisdiction Routing Rationale
          </div>
          <p className="text-gray-700 leading-relaxed">{alert.routing_reason}</p>
        </div>
      )}

      {/* Recipient Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Destination 1: Originating Department */}
        <div className="border border-gray-200 rounded-lg p-4 bg-gray-50/50 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-blue-700 bg-blue-100/60 px-2 py-0.5 rounded">
              Destination 1: Originating Department
            </span>
          </div>
          <div className="text-sm font-bold text-gray-900">
            {alert.originating_department_name || `Department #${alert.originating_department_id}`}
          </div>
          <p className="text-xs text-gray-500">
            Registered and maintains Case <strong className="text-gray-700">{alert.case_number}</strong>.
          </p>
        </div>

        {/* Destination 2: Nearest Authorized Department */}
        <div className="border border-gray-200 rounded-lg p-4 bg-gray-50/50 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-700 bg-indigo-100/60 px-2 py-0.5 rounded">
              Destination 2: Nearest Authorized Department
            </span>
            {alert.distance_km != null && (
              <span className="text-xs font-semibold text-gray-600">
                {alert.distance_km} km away
              </span>
            )}
          </div>
          <div className="text-sm font-bold text-gray-900">
            {alert.nearest_department_name || (alert.nearest_department_id ? `Department #${alert.nearest_department_id}` : 'Same as Originating')}
          </div>
          <p className="text-xs text-gray-500">
            Responsible operational facility closest to camera <strong className="text-gray-700">{alert.detected_camera_code || 'location'}</strong>.
          </p>
        </div>
      </div>

      {/* Recipient Notification Records */}
      <div className="space-y-2 pt-2">
        <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider">
          Transmission Status per Department
        </h4>
        <div className="border border-gray-200 rounded-md divide-y divide-gray-100 overflow-hidden">
          {alert.recipients.map((recip) => (
            <div key={recip.id} className="p-3 flex items-center justify-between bg-white text-xs">
              <div className="flex items-center gap-3">
                <div className="p-1.5 rounded-full bg-gray-100 text-gray-600">
                  {recip.delivery_channel === 'EMAIL' ? (
                    <Mail className="w-3.5 h-3.5" />
                  ) : (
                    <Building2 className="w-3.5 h-3.5" />
                  )}
                </div>
                <div>
                  <div className="font-semibold text-gray-900">
                    {recip.recipient_type.replace(/_/g, ' ')} ({recip.delivery_channel})
                  </div>
                  <div className="text-gray-400 text-[11px]">
                    Destination: {recip.destination_reference || 'In-App Secure Channel'}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <AlertStatusBadge status={recip.status} size="sm" />
                {recip.acknowledged_at && (
                  <span className="text-[11px] text-green-700 flex items-center gap-1 font-medium bg-green-50 px-2 py-0.5 rounded border border-green-200">
                    <CheckCircle2 className="w-3 h-3 text-green-600" /> Acknowledged
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
