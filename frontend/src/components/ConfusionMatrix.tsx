/**
 * ConfusionMatrix – Visual 2×2 confusion matrix for evaluation results.
 * 
 * Displays TP, FP, TN, FN with derived metrics (Precision, Recall, F1, FMR, FNMR).
 * Includes the required research disclaimer.
 */

interface ConfusionMatrixProps {
  tp: number;
  fp: number;
  tn: number;
  fn: number;
  precision?: number | null;
  recall?: number | null;
  f1Score?: number | null;
  fmr?: number | null;
  fnmr?: number | null;
  disclaimer?: string;
}

function pct(val: number | null | undefined): string {
  if (val === null || val === undefined) return '—';
  return `${(val * 100).toFixed(2)}%`;
}

export default function ConfusionMatrix({
  tp,
  fp,
  tn,
  fn,
  precision,
  recall,
  f1Score,
  fmr,
  fnmr,
  disclaimer,
}: ConfusionMatrixProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Confusion Matrix</h3>

      {/* Matrix grid */}
      <div className="mb-5">
        {/* Column headers */}
        <div className="grid grid-cols-3 gap-1 mb-1">
          <div />
          <div className="text-center text-xs font-semibold text-gray-500">Predicted Match</div>
          <div className="text-center text-xs font-semibold text-gray-500">Predicted No Match</div>
        </div>
        {/* Row: Actual Match */}
        <div className="grid grid-cols-3 gap-1 mb-1">
          <div className="flex items-center justify-end pr-2">
            <span className="text-xs font-semibold text-gray-500 text-right">Actual Match</span>
          </div>
          <div className="bg-green-50 border-2 border-green-200 rounded-lg p-3 text-center">
            <div className="text-xl font-bold text-green-700">{tp}</div>
            <div className="text-xs font-medium text-green-600 mt-0.5">True Positive</div>
          </div>
          <div className="bg-red-50 border-2 border-red-200 rounded-lg p-3 text-center">
            <div className="text-xl font-bold text-red-700">{fn}</div>
            <div className="text-xs font-medium text-red-600 mt-0.5">False Negative</div>
          </div>
        </div>
        {/* Row: Actual No Match */}
        <div className="grid grid-cols-3 gap-1">
          <div className="flex items-center justify-end pr-2">
            <span className="text-xs font-semibold text-gray-500 text-right">Actual No Match</span>
          </div>
          <div className="bg-orange-50 border-2 border-orange-200 rounded-lg p-3 text-center">
            <div className="text-xl font-bold text-orange-700">{fp}</div>
            <div className="text-xs font-medium text-orange-600 mt-0.5">False Positive</div>
          </div>
          <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-3 text-center">
            <div className="text-xl font-bold text-blue-700">{tn}</div>
            <div className="text-xs font-medium text-blue-600 mt-0.5">True Negative</div>
          </div>
        </div>
      </div>

      {/* Derived metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mt-4">
        {[
          { label: 'Precision', value: pct(precision), color: 'text-green-700' },
          { label: 'Recall',    value: pct(recall),    color: 'text-blue-700'  },
          { label: 'F1 Score',  value: pct(f1Score),   color: 'text-purple-700' },
          { label: 'FMR',       value: pct(fmr),       color: 'text-orange-700' },
          { label: 'FNMR',      value: pct(fnmr),      color: 'text-red-700'   },
        ].map((m) => (
          <div key={m.label} className="bg-gray-50 rounded-lg px-3 py-2 text-center border border-gray-100">
            <div className={`text-lg font-bold ${m.color}`}>{m.value}</div>
            <div className="text-xs text-gray-500 font-medium mt-0.5">{m.label}</div>
          </div>
        ))}
      </div>

      {/* Disclaimer */}
      {disclaimer && (
        <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-xs text-yellow-800 leading-snug">
            <span className="font-semibold">⚠ Research Disclaimer: </span>
            {disclaimer}
          </p>
        </div>
      )}
    </div>
  );
}
