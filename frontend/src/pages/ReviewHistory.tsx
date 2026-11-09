import { useEffect, useState } from "react";
import { format } from 'date-fns';
import { History, Search } from 'lucide-react';
import { listReviewEvents } from '../services/reviewApi';
import type { ReviewEventSummary } from '../types/review';
import { StatusBadge } from '../components/StatusBadge';
import { useNavigate } from 'react-router-dom';

export default function ReviewHistory() {
  const [events, setEvents] = useState<ReviewEventSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        setLoading(true);
        // Fetch completed/terminal events
        const confirmed = await listReviewEvents({ status: 'CONFIRMED_FOR_ACTION' }, 20);
        const rejected = await listReviewEvents({ status: 'REJECTED' }, 20);
        
        // Combine and sort by date desc
        const all = [...confirmed, ...rejected].sort((a, b) => 
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        );
        
        setEvents(all);
      } catch (error) {
        console.error('Failed to fetch history', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchHistory();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <History className="w-6 h-6 text-blue-600" />
          Review Activity History
        </h1>
        <p className="text-sm text-gray-500">Audit log of completed human verification reviews</p>
      </div>

      <div className="bg-white p-4 rounded-lg shadow border border-gray-200">
        <div className="bg-gray-50 p-3 rounded mb-4 text-sm text-gray-600 flex items-center gap-2 border border-gray-200">
           <Search className="w-4 h-4" />
           Showing recent completed reviews. For full audit trail of a specific case, search in the dashboard.
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading history...</div>
        ) : events.length === 0 ? (
          <div className="p-12 text-center text-gray-500 border border-dashed rounded">
            No completed reviews found in history.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date / Time</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Case Number</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Event ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Decision Result</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Examiner</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {events.map((event) => (
                  <tr 
                    key={event.id} 
                    onClick={() => navigate(`/review/${event.id}`)}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {format(new Date(event.updated_at), 'PP pp')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap font-bold text-gray-900">
                      {event.case_number}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-500">
                      {event.match_event_id.substring(0, 8)}...
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={event.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {event.assigned_to ? `Officer ${event.assigned_to}` : 'System'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
