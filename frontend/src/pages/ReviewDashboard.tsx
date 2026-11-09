import React, { useEffect, useState } from 'react';
import { Search, Filter, RefreshCw } from 'lucide-react';
import type { ReviewEventSummary, ReviewDashboardStats, Filters } from '../types/review';
import { getDashboardStats, listReviewEvents } from '../services/reviewApi';
import { MatchCard } from '../components/MatchCard';

export default function ReviewDashboard() {
  const [stats, setStats] = useState<ReviewDashboardStats | null>(null);
  const [events, setEvents] = useState<ReviewEventSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Filters>({
    status: 'PENDING_REVIEW',
  });
  const [activeTab, setActiveTab] = useState('pending');

  const fetchData = async () => {
    try {
      setLoading(true);
      const [statsData, eventsData] = await Promise.all([
        getDashboardStats(),
        listReviewEvents(filters)
      ]);
      setStats(statsData);
      setEvents(eventsData);
    } catch (error) {
      console.error('Failed to fetch dashboard data', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [filters]);

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    if (tab === 'pending') {
      setFilters({ ...filters, status: 'PENDING_REVIEW' });
    } else if (tab === 'high_priority') {
      setFilters({ ...filters, status: 'PENDING_REVIEW', priority: 'HIGH' });
    } else {
      setFilters({ ...filters, status: '' });
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">AI SURVEILLANCE REVIEW DASHBOARD</h1>
        <p className="text-sm text-gray-500">Module 8 — Human Verification & Investigation</p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatCard title="Pending Review" value={stats.pending_review} color="amber" />
          <StatCard title="Under Review" value={stats.under_review} color="blue" />
          <StatCard title="Confirmed" value={stats.confirmed_for_action} color="green" />
          <StatCard title="Need Evidence" value={stats.need_more_evidence} color="purple" />
          <StatCard title="Missing Category" value={stats.missing_category_count} color="orange" />
          <StatCard title="Wanted Category" value={stats.wanted_category_count} color="red" />
        </div>
      )}

      <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
        <div className="flex flex-col sm:flex-row gap-4 justify-between items-center mb-4">
          <div className="flex space-x-1 bg-gray-100 p-1 rounded-lg">
            <TabButton active={activeTab === 'pending'} onClick={() => handleTabChange('pending')}>
              Pending Reviews
            </TabButton>
            <TabButton active={activeTab === 'high_priority'} onClick={() => handleTabChange('high_priority')}>
              High Priority
            </TabButton>
            <TabButton active={activeTab === 'all'} onClick={() => handleTabChange('all')}>
              All Events
            </TabButton>
          </div>
          
          <div className="flex gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:w-64">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search className="h-4 w-4 text-gray-400" />
              </div>
              <input
                type="text"
                placeholder="Search case, event ID..."
                value={filters.search || ''}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                className="pl-9 w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-2 border"
              />
            </div>
            <button 
              onClick={() => fetchData()}
              className="p-2 border border-gray-300 rounded-md text-gray-600 hover:bg-gray-50"
              title="Refresh data"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
        
        <div className="flex flex-wrap gap-3 mb-6 items-center text-sm border-t pt-4">
          <Filter className="w-4 h-4 text-gray-500" />
          <select 
            value={filters.category || ''}
            onChange={(e) => setFilters({ ...filters, category: e.target.value as any })}
            className="border-gray-300 rounded-md text-sm border p-1.5"
          >
            <option value="">All Categories</option>
            <option value="MISSING">Missing</option>
            <option value="WANTED">Wanted</option>
          </select>
          
          <select 
            value={filters.status || ''}
            onChange={(e) => setFilters({ ...filters, status: e.target.value as any })}
            className="border-gray-300 rounded-md text-sm border p-1.5"
          >
            <option value="">All Statuses</option>
            <option value="PENDING_REVIEW">Pending Review</option>
            <option value="UNDER_REVIEW">Under Review</option>
            <option value="CONFIRMED_FOR_ACTION">Confirmed</option>
            <option value="REJECTED">Rejected</option>
            <option value="NEED_MORE_EVIDENCE">Need Evidence</option>
          </select>
        </div>

        {loading && events.length === 0 ? (
          <div className="flex justify-center items-center h-64 text-gray-500">
            <RefreshCw className="w-6 h-6 animate-spin mr-2" />
            Loading queue...
          </div>
        ) : events.length === 0 ? (
          <div className="flex flex-col justify-center items-center h-64 text-gray-500 bg-gray-50 rounded border border-dashed">
            <p>No events found matching your filters.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {events.map((event) => (
              <MatchCard key={event.id} event={event} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ title, value, color }: { title: string, value: number, color: string }) {
  const colorMap: Record<string, string> = {
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    blue: 'bg-blue-50 border-blue-200 text-blue-700',
    green: 'bg-green-50 border-green-200 text-green-700',
    purple: 'bg-purple-50 border-purple-200 text-purple-700',
    orange: 'bg-orange-50 border-orange-200 text-orange-700',
    red: 'bg-red-50 border-red-200 text-red-700',
  };
  
  return (
    <div className={`p-4 rounded-lg border ${colorMap[color]}`}>
      <p className="text-xs font-medium uppercase tracking-wider opacity-80 mb-1">{title}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

function TabButton({ active, children, onClick }: { active: boolean, children: React.ReactNode, onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
        active 
          ? 'bg-white text-gray-900 shadow-sm' 
          : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
      }`}
    >
      {children}
    </button>
  );
}
