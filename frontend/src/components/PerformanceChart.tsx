/**
 * PerformanceChart – A pure-CSS bar chart for analytics performance metrics.
 * 
 * Renders horizontal or vertical bars for a list of labelled values.
 * Uses only Tailwind/inline styles — no chart library required.
 */

interface BarItem {
  label: string;
  value: number;
  maxValue?: number;
  color?: string;
}

interface PerformanceChartProps {
  title: string;
  items: BarItem[];
  /** Overall max across all items (auto-computed if omitted) */
  globalMax?: number;
  showValues?: boolean;
  valueFormatter?: (v: number) => string;
  emptyMessage?: string;
}

export default function PerformanceChart({
  title,
  items,
  globalMax,
  showValues = true,
  valueFormatter = (v) => v.toLocaleString(),
  emptyMessage = 'No data available.',
}: PerformanceChartProps) {
  const max = globalMax ?? Math.max(...items.map((i) => i.value), 1);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">{title}</h3>

      {items.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">{emptyMessage}</p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const pct = max > 0 ? (item.value / max) * 100 : 0;
            const barColor = item.color ?? 'bg-blue-500';

            return (
              <div key={item.label} className="group">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-xs font-medium text-gray-600 truncate max-w-[60%]">
                    {item.label}
                  </span>
                  {showValues && (
                    <span className="text-xs font-semibold text-gray-700 ml-2 flex-shrink-0">
                      {valueFormatter(item.value)}
                    </span>
                  )}
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                  <div
                    className={`${barColor} h-2 rounded-full transition-all duration-500`}
                    style={{ width: `${Math.min(pct, 100)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
