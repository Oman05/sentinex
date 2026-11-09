/**
 * MetricCard – Reusable metric display card for analytics dashboards.
 * Displays a labelled metric with optional trend indicator and tooltip.
 */

import { type LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number | null;
  icon?: LucideIcon;
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'gray';
  suffix?: string;
  description?: string;
  size?: 'sm' | 'md' | 'lg';
}

const colorMap = {
  blue:   { bg: 'bg-blue-50',   icon: 'text-blue-500',   value: 'text-blue-700',  border: 'border-blue-100' },
  green:  { bg: 'bg-green-50',  icon: 'text-green-500',  value: 'text-green-700', border: 'border-green-100' },
  yellow: { bg: 'bg-yellow-50', icon: 'text-yellow-500', value: 'text-yellow-700',border: 'border-yellow-100' },
  red:    { bg: 'bg-red-50',    icon: 'text-red-500',    value: 'text-red-700',   border: 'border-red-100' },
  purple: { bg: 'bg-purple-50', icon: 'text-purple-500', value: 'text-purple-700',border: 'border-purple-100' },
  gray:   { bg: 'bg-gray-50',   icon: 'text-gray-400',   value: 'text-gray-700',  border: 'border-gray-200' },
};

export default function MetricCard({
  label,
  value,
  icon: Icon,
  color = 'blue',
  suffix,
  description,
  size = 'md',
}: MetricCardProps) {
  const colors = colorMap[color];
  const displayValue = value === null || value === undefined ? '—' : value;

  return (
    <div className={`bg-white rounded-xl border ${colors.border} p-4 shadow-sm hover:shadow-md transition-shadow`}>
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider truncate">{label}</p>
          <div className="mt-1 flex items-baseline gap-1">
            <span
              className={`font-bold ${colors.value} ${
                size === 'lg' ? 'text-3xl' : size === 'sm' ? 'text-lg' : 'text-2xl'
              }`}
            >
              {displayValue}
            </span>
            {suffix && <span className="text-sm text-gray-500 font-medium">{suffix}</span>}
          </div>
          {description && (
            <p className="mt-1 text-xs text-gray-400 leading-snug">{description}</p>
          )}
        </div>
        {Icon && (
          <div className={`p-2 rounded-lg ${colors.bg} ml-3 flex-shrink-0`}>
            <Icon className={`w-5 h-5 ${colors.icon}`} />
          </div>
        )}
      </div>
    </div>
  );
}
