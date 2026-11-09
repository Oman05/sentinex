import { useEffect, useState } from "react";
import { format } from 'date-fns';
import { ClipboardList, Plus } from 'lucide-react';
import type { InvestigationTask } from '../types/review';
import { listTasks } from '../services/reviewApi';
import { StatusBadge } from '../components/StatusBadge';

export default function InvestigationTasks() {
  const [tasks, setTasks] = useState<InvestigationTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ status: '', assigned_to: '' });

  useEffect(() => {
    const fetchTasks = async () => {
      try {
        setLoading(true);
        const data = await listTasks({ ...filters, assigned_to: filters.assigned_to ? parseInt(filters.assigned_to) : undefined });
        setTasks(data);
      } catch (error) {
        console.error('Failed to fetch tasks', error);
      } finally {
        setLoading(false);
      }
    };
    fetchTasks();
  }, [filters]);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <ClipboardList className="w-6 h-6 text-blue-600" />
            Investigation Tasks
          </h1>
          <p className="text-sm text-gray-500">Manage follow-up actions for confirmed matches</p>
        </div>
        <button className="bg-blue-600 text-white px-4 py-2 rounded flex items-center gap-2 hover:bg-blue-700 text-sm font-medium">
          <Plus className="w-4 h-4" /> Create Task
        </button>
      </div>

      <div className="bg-white p-4 rounded-lg shadow border border-gray-200">
        <div className="flex gap-4 mb-4">
          <select 
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className="border-gray-300 rounded-md text-sm border p-2"
          >
            <option value="">All Statuses</option>
            <option value="OPEN">Open</option>
            <option value="ASSIGNED">Assigned</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="COMPLETED">Completed</option>
          </select>
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading tasks...</div>
        ) : tasks.length === 0 ? (
          <div className="p-12 text-center text-gray-500 bg-gray-50 border border-dashed rounded">
            No investigation tasks found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Case / Title</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Priority</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Assigned</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Due Date</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {tasks.map((task) => (
                  <tr key={task.id} className="hover:bg-gray-50 cursor-pointer">
                    <td className="px-6 py-4">
                      <div className="text-sm font-bold text-gray-900 mb-1">{task.case_number}</div>
                      <div className="text-sm text-gray-600">{task.title}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={task.priority} type="priority" />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={task.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {task.assigned_to ? `Officer ${task.assigned_to}` : 'Unassigned'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {task.due_date ? format(new Date(task.due_date), 'PP') : '-'}
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
