import { useEffect, useState } from 'react';
import { Server, RotateCw, RefreshCw, CheckCircle2, AlertTriangle, Clock, Layers } from 'lucide-react';
import { getWorkerStatus, restartWorker } from '../services/adminApi';
import type { WorkerStatusItem } from '../types/admin';

export default function AdminWorkerMonitor() {
  const [workers, setWorkers] = useState<WorkerStatusItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [restarting, setRestarting] = useState<string | null>(null);

  const fetchWorkers = async () => {
    setLoading(true);
    try {
      const data = await getWorkerStatus();
      setWorkers(data);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to fetch background worker telemetry');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkers();
    const interval = setInterval(fetchWorkers, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRestart = async (workerName: string) => {
    setRestarting(workerName);
    try {
      await restartWorker(workerName);
      fetchWorkers();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to restart worker');
    } finally {
      setRestarting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Server className="w-6 h-6 text-blue-600" />
            Background Task Queues &amp; Asynchronous Worker Fleet
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Real-time pipeline monitoring for CCTV ingestion, YOLO inference, vector matching, and alert dispatchers.
          </p>
        </div>
        <button
          onClick={fetchWorkers}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition"
        >
          <RotateCw className="w-4 h-4" />
          Refresh Fleet
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {loading && workers.length === 0 ? (
          <div className="col-span-2 p-12 text-center">
            <RotateCw className="w-8 h-8 animate-spin mx-auto text-blue-600" />
          </div>
        ) : (
          workers.map((w) => {
            const isError = w.status === 'ERROR';
            const isBusy = w.status === 'BUSY';

            return (
              <div
                key={w.worker_name}
                className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm flex flex-col justify-between space-y-4"
              >
                <div>
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-sm font-bold text-gray-900">{w.display_name}</h3>
                      <span className="font-mono text-xs text-gray-400">{w.worker_name}</span>
                    </div>
                    <span
                      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold ${
                        isError
                          ? 'bg-red-100 text-red-800'
                          : isBusy
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-green-100 text-green-800'
                      }`}
                    >
                      {isError ? (
                        <AlertTriangle className="w-3.5 h-3.5 text-red-600" />
                      ) : (
                        <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
                      )}
                      {w.status}
                    </span>
                  </div>

                  {w.current_job && (
                    <div className="mt-2 text-xs bg-blue-50 text-blue-700 p-2 rounded border border-blue-100">
                      Processing: <span className="font-mono font-medium">{w.current_job}</span>
                    </div>
                  )}

                  {w.last_error && (
                    <div className="mt-2 text-xs bg-red-50 text-red-700 p-2 rounded border border-red-200">
                      Error: {w.last_error}
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-2 pt-3 border-t border-gray-100 text-xs">
                  <div>
                    <span className="text-gray-400 block flex items-center gap-1">
                      <Layers className="w-3 h-3" /> Queue Size
                    </span>
                    <span className="font-bold text-gray-800">{w.queue_size}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 block flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3 text-green-500" /> Processed
                    </span>
                    <span className="font-bold text-gray-800">{w.jobs_processed}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 block flex items-center gap-1">
                      <Clock className="w-3 h-3" /> Latency
                    </span>
                    <span className="font-bold text-gray-800">{w.avg_processing_time_ms} ms</span>
                  </div>
                </div>

                <div className="flex justify-between items-center pt-2">
                  <span className="text-[11px] text-gray-400">
                    Heartbeat: {new Date(w.last_heartbeat).toLocaleTimeString()}
                  </span>
                  <button
                    onClick={() => handleRestart(w.worker_name)}
                    disabled={restarting === w.worker_name}
                    className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${restarting === w.worker_name ? 'animate-spin' : ''}`} />
                    Restart / Clear
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
