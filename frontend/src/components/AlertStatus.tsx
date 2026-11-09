import React from 'react';
import type { AlertPriority, AlertStatus as AlertStatusType } from '../types/alert';

export const AlertStatusBadge: React.FC<{ status: AlertStatusType | string; size?: 'sm' | 'md' }> = ({
  status,
  size = 'md',
}) => {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  const getStatusStyles = () => {
    switch (status) {
      case 'CREATED':
      case 'QUEUED':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'SENT':
        return 'bg-sky-50 text-sky-700 border-sky-200';
      case 'DELIVERED':
        return 'bg-indigo-50 text-indigo-700 border-indigo-200';
      case 'ACKNOWLEDGED':
        return 'bg-amber-50 text-amber-700 border-amber-300 font-semibold';
      case 'IN_PROGRESS':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'RESOLVED':
        return 'bg-emerald-50 text-emerald-700 border-emerald-300';
      case 'CLOSED':
        return 'bg-gray-100 text-gray-700 border-gray-300';
      case 'FAILED':
        return 'bg-red-50 text-red-700 border-red-200';
      default:
        return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium tracking-wide ${sizeClasses} ${getStatusStyles()}`}
    >
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-70"></span>
      {status.replace(/_/g, ' ')}
    </span>
  );
};

export const AlertPriorityBadge: React.FC<{ priority: AlertPriority | string; size?: 'sm' | 'md' }> = ({
  priority,
  size = 'md',
}) => {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  const getPriorityStyles = () => {
    switch (priority) {
      case 'CRITICAL':
        return 'bg-red-100 text-red-800 border-red-300 font-bold animate-pulse';
      case 'HIGH':
        return 'bg-orange-100 text-orange-800 border-orange-300 font-semibold';
      case 'NORMAL':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'LOW':
        return 'bg-gray-100 text-gray-600 border-gray-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${sizeClasses} ${getPriorityStyles()}`}
    >
      {priority}
    </span>
  );
};
