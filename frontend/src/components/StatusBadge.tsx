import React from 'react';

interface StatusBadgeProps {
  status: string;
  type?: 'review' | 'category' | 'priority';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, type = 'review' }) => {
  const getColors = () => {
    if (type === 'category') {
      switch (status) {
        case 'MISSING': return 'bg-orange-100 text-orange-800 border-orange-200';
        case 'WANTED': return 'bg-red-100 text-red-800 border-red-200';
        default: return 'bg-gray-100 text-gray-800 border-gray-200';
      }
    }
    
    if (type === 'priority') {
      switch (status) {
        case 'LOW': return 'bg-green-100 text-green-800 border-green-200';
        case 'MEDIUM': return 'bg-blue-100 text-blue-800 border-blue-200';
        case 'HIGH': return 'bg-orange-100 text-orange-800 border-orange-200';
        case 'URGENT': return 'bg-red-100 text-red-800 border-red-200';
        default: return 'bg-gray-100 text-gray-800 border-gray-200';
      }
    }

    switch (status) {
      case 'PENDING_REVIEW': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'UNDER_REVIEW': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'CONFIRMED_FOR_ACTION': return 'bg-green-100 text-green-800 border-green-200';
      case 'REJECTED': return 'bg-red-100 text-red-800 border-red-200';
      case 'NEED_MORE_EVIDENCE': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'OPEN': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'ASSIGNED': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'IN_PROGRESS': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'COMPLETED': return 'bg-green-100 text-green-800 border-green-200';
      case 'CANCELLED': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getLabel = () => {
    return status.replace(/_/g, ' ');
  };

  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${getColors()}`}>
      {getLabel()}
    </span>
  );
};
