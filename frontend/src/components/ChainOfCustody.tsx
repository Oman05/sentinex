import React from 'react';
import { Shield, ArrowDown, User, Info, CheckCircle2 } from 'lucide-react';
import type { CustodyEvent } from '../types/evidence';

interface ChainOfCustodyProps {
  evidenceId: string;
  evidenceType: string;
  caseNumber?: string | null;
  events: CustodyEvent[];
  disclaimer: string;
  isLoading?: boolean;
}

export const ChainOfCustody: React.FC<ChainOfCustodyProps> = ({
  evidenceId,
  evidenceType,
  caseNumber,
  events,
  disclaimer,
  isLoading,
}) => {
  if (isLoading) {
    return (
      <div className="p-8 text-center text-gray-500 animate-pulse">
        Generating chain-of-custody audit sequence...
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="p-5 bg-slate-900 text-white flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-400" />
            <h3 className="font-bold text-sm tracking-wide">CHAIN OF CUSTODY AUDIT TRAIL</h3>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Subject Item: <strong className="text-white font-mono">{evidenceId}</strong> ({evidenceType})
            {caseNumber ? ` • Case Docket ${caseNumber}` : ''}
          </p>
        </div>
        <span className="text-[11px] bg-slate-800 border border-slate-700 text-slate-300 px-3 py-1 rounded-full font-medium">
          {events.length} Custodial Transitions
        </span>
      </div>

      {/* Prominent Legal Disclaimer Alert (Section 21) */}
      <div className="bg-amber-50 border-b border-amber-200 p-3.5 flex items-start gap-3">
        <Info className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
        <div className="text-xs text-amber-900 leading-relaxed">
          <strong className="font-semibold block mb-0.5">ADMINISTRATIVE AUDIT TRAIL NOTICE:</strong>
          {disclaimer}
        </div>
      </div>

      {/* Custody Sequence */}
      <div className="p-6">
        <div className="max-w-2xl mx-auto space-y-4">
          {events.map((evt, idx) => (
            <React.Fragment key={idx}>
              <div className="border border-gray-200 rounded-lg p-4 bg-gray-50/50 hover:bg-white transition-colors shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-800 px-2 py-0.5 bg-slate-200 rounded">
                    Step {idx + 1}: {evt.action}
                  </span>
                  <span className="text-xs font-mono text-gray-500">
                    {new Date(evt.timestamp).toLocaleString()}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs mt-3">
                  <div>
                    <span className="text-gray-400 block text-[10px] uppercase font-semibold">Custodial Actor</span>
                    <span className="font-medium text-gray-800 flex items-center gap-1 mt-0.5">
                      <User className="w-3.5 h-3.5 text-gray-500" />
                      {evt.actor || 'SYSTEM AUTOMATION'}
                    </span>
                  </div>

                  {evt.reason && (
                    <div>
                      <span className="text-gray-400 block text-[10px] uppercase font-semibold">Stated Rationale</span>
                      <span className="text-gray-700 italic block mt-0.5">{evt.reason}</span>
                    </div>
                  )}

                  {evt.source && (
                    <div>
                      <span className="text-gray-400 block text-[10px] uppercase font-semibold">Source State / Location</span>
                      <span className="font-mono text-gray-700 block mt-0.5 truncate">{evt.source}</span>
                    </div>
                  )}

                  {evt.destination && (
                    <div>
                      <span className="text-gray-400 block text-[10px] uppercase font-semibold">Destination / Target</span>
                      <span className="font-mono text-gray-700 block mt-0.5 truncate">{evt.destination}</span>
                    </div>
                  )}
                </div>

                {evt.integrity_info && (
                  <div className="mt-3 pt-2.5 border-t border-gray-200 text-xs text-gray-600 flex items-center gap-1.5 font-mono">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                    <span className="truncate">{evt.integrity_info}</span>
                  </div>
                )}
              </div>

              {idx < events.length - 1 && (
                <div className="flex justify-center my-1 text-gray-400">
                  <ArrowDown className="w-4 h-4 animate-bounce" />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
};
