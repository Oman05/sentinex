/**
 * LiveCameraDemo – Laptop Front Camera Live Detection Dashboard
 *
 * Workflow:
 *  1. User selects (or registers) the laptop webcam camera (stream_url = "0")
 *  2. Start Camera → backend opens VideoCapture(0) via the existing StreamWorker
 *  3. MJPEG feed is rendered via <img src="/api/cameras/{id}/stream">
 *  4. AI pipeline detects faces and compares against enrolled reference embeddings
 *  5. Candidate matches appear in the Review Dashboard (human confirmation required)
 *
 * AI Safety: All outputs are labelled "POSSIBLE MATCH — HUMAN VERIFICATION REQUIRED"
 * and require authorized human review before any alert is dispatched.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Camera, Play, Square, RefreshCw, AlertTriangle,
  CheckCircle, XCircle, Info, Eye, Wifi, WifiOff,
  Activity,
} from 'lucide-react';
import {
  listAdminCameras,
  listAdminDepartments,
  createAdminCamera,
  startCameraStream,
  stopCameraStream,
  getCameraStreamStatus,
} from '../services/adminApi';
import { listReviewEvents } from '../services/reviewApi';
import type { AdminCamera, AdminDepartment } from '../types/admin';
import type { ReviewEventSummary } from '../types/review';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type StreamState = 'IDLE' | 'CONNECTING' | 'LIVE' | 'STOPPED' | 'ERROR';

interface StreamStatus {
  db_status: string;
  live_status: string;
  is_streaming: boolean;
  is_pipeline_active: boolean;
  last_frame_at: string | null;
  last_error: string | null;
  failures: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace(/\/api$/, '');
const token = () => localStorage.getItem('sentinex_token') || '';

function statusColor(state: StreamState): string {
  switch (state) {
    case 'LIVE': return 'bg-green-500';
    case 'CONNECTING': return 'bg-yellow-400 animate-pulse';
    case 'ERROR': return 'bg-red-500';
    case 'STOPPED': return 'bg-gray-400';
    default: return 'bg-gray-300';
  }
}

function statusLabel(state: StreamState): string {
  switch (state) {
    case 'LIVE': return 'LIVE';
    case 'CONNECTING': return 'CONNECTING…';
    case 'ERROR': return 'ERROR';
    case 'STOPPED': return 'STOPPED';
    default: return 'IDLE';
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function LiveCameraDemo() {
  const [cameras, setCameras] = useState<AdminCamera[]>([]);
  const [departments, setDepartments] = useState<AdminDepartment[]>([]);
  const [selectedCamera, setSelectedCamera] = useState<AdminCamera | null>(null);
  const [streamState, setStreamState] = useState<StreamState>('IDLE');
  const [statusDetail, setStatusDetail] = useState<StreamStatus | null>(null);
  const [candidateMatches, setCandidateMatches] = useState<ReviewEventSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [imgKey, setImgKey] = useState(0); // force-reload img on stream start

  // Registration form state
  const [showRegister, setShowRegister] = useState(false);
  const [registerForm, setRegisterForm] = useState({
    camera_name: 'Laptop Front Camera',
    department_id: '',
    location_name: 'Demo Station – Laptop Front Camera',
    stream_url: '0',
    stream_type: 'WEBCAM',
    sample_fps: 1.0,
  });
  const [registering, setRegistering] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ------------------------------------------------------------------
  // Data fetching
  // ------------------------------------------------------------------
  const fetchData = useCallback(async () => {
    try {
      const [cams, depts] = await Promise.all([
        listAdminCameras(),
        listAdminDepartments(),
      ]);
      // Show only WEBCAM cameras first, then all
      const webcams = cams.filter(
        (c) => c.stream_type === 'WEBCAM' || /^\d+$/.test((c as any).stream_url || '')
      );
      setCameras(cams);
      setDepartments(depts);

      // Auto-select the first webcam if none selected
      if (!selectedCamera && webcams.length > 0) {
        setSelectedCamera(webcams[0]);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load cameras');
    }
  }, [selectedCamera]);

  useEffect(() => {
    fetchData();
  }, []);

  // ------------------------------------------------------------------
  // Stream status and candidate matches polling
  // ------------------------------------------------------------------
  const pollStatus = useCallback(async () => {
    if (!selectedCamera) return;
    try {
      const s: StreamStatus = await getCameraStreamStatus(selectedCamera.id);
      setStatusDetail(s);
      const lv = (s.live_status || '').toUpperCase();
      if (lv === 'ONLINE') setStreamState('LIVE');
      else if (lv === 'CONNECTING') setStreamState('CONNECTING');
      else if (lv === 'ERROR') setStreamState('ERROR');
      else if (lv === 'OFFLINE') setStreamState('STOPPED');

      // Poll recent candidate match events for this camera
      try {
        const matches = await listReviewEvents({ camera_id: String(selectedCamera.id) }, 10, 0);
        setCandidateMatches(matches || []);
      } catch {
        // non-blocking
      }
    } catch {
      // silent – camera might not have been started yet
    }
  }, [selectedCamera]);

  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (selectedCamera) {
      pollStatus();
      pollRef.current = setInterval(pollStatus, 2000);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [selectedCamera, pollStatus]);

  // ------------------------------------------------------------------
  // Stream controls
  // ------------------------------------------------------------------
  const handleStart = async () => {
    if (!selectedCamera) return;
    setLoading(true);
    setError(null);
    setStreamState('CONNECTING');
    try {
      await startCameraStream(selectedCamera.id);
      // Wait briefly then force-reload the MJPEG img
      setTimeout(() => {
        setImgKey((k) => k + 1);
        setStreamState('CONNECTING');
      }, 800);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to start camera stream');
      setStreamState('ERROR');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    if (!selectedCamera) return;
    setLoading(true);
    setError(null);
    try {
      await stopCameraStream(selectedCamera.id);
      setStreamState('STOPPED');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to stop camera stream');
    } finally {
      setLoading(false);
    }
  };

  // ------------------------------------------------------------------
  // Register webcam
  // ------------------------------------------------------------------
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!registerForm.department_id) {
      alert('Please select a department');
      return;
    }
    setRegistering(true);
    try {
      await createAdminCamera({
        camera_name: registerForm.camera_name,
        department_id: parseInt(registerForm.department_id),
        location_name: registerForm.location_name,
        stream_url: registerForm.stream_url,
        stream_type: registerForm.stream_type,
        sample_fps: registerForm.sample_fps,
        sampling_interval: 1.0,
      });
      setShowRegister(false);
      await fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to register camera');
    } finally {
      setRegistering(false);
    }
  };

  // ------------------------------------------------------------------
  // MJPEG stream URL (auth token injected as query param)
  // ------------------------------------------------------------------
  const streamUrl = selectedCamera
    ? `${BASE_URL}/api/cameras/${selectedCamera.id}/stream?token=${token()}&_t=${imgKey}`
    : null;

  const isRunning = streamState === 'LIVE' || streamState === 'CONNECTING';
  const webcamCameras = cameras.filter(
    (c) => c.stream_type === 'WEBCAM' || /^\d+$/.test((c as any).stream_url || '')
  );

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <Camera className="w-6 h-6 text-blue-600" />
              Live Camera Demo — Laptop Front Camera
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              Real-time face detection and candidate matching against enrolled Missing / Wanted persons.
              All detections require authorized human verification before any alert is dispatched.
            </p>
          </div>
          <button
            onClick={() => setShowRegister(true)}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition"
          >
            + Register Webcam
          </button>
        </div>
      </div>

      {/* AI Safety Notice */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-amber-800">
          <span className="font-semibold">AI Safety Notice: </span>
          All face matches are labelled <em>POSSIBLE MATCH — HUMAN VERIFICATION REQUIRED</em>.
          The system does not automatically confirm identity or dispatch alerts.
          Only enrol consenting test participants under fictional case IDs for demonstration.
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg text-sm flex items-center gap-2">
          <XCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Camera selector + controls */}
        <div className="space-y-4">
          {/* Camera selector */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <Wifi className="w-4 h-4" /> Select Camera
            </h2>
            {webcamCameras.length === 0 ? (
              <div className="text-sm text-gray-500 italic">
                No webcam cameras registered. Click <strong>Register Webcam</strong> above.
              </div>
            ) : (
              <div className="space-y-2">
                {webcamCameras.map((cam) => (
                  <button
                    key={cam.id}
                    onClick={() => {
                      setSelectedCamera(cam);
                      setStreamState('IDLE');
                    }}
                    className={`w-full text-left px-3 py-2.5 rounded-md border text-sm transition ${
                      selectedCamera?.id === cam.id
                        ? 'bg-blue-50 border-blue-300 text-blue-800 font-medium'
                        : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <div className="font-medium">{cam.camera_name}</div>
                    <div className="text-xs text-gray-400 mt-0.5">{cam.location_name || 'No location'}</div>
                    <div className="flex items-center gap-1.5 mt-1">
                      <span className={`w-2 h-2 rounded-full inline-block ${
                        cam.status === 'ONLINE' ? 'bg-green-500' :
                        cam.status === 'CONNECTING' ? 'bg-yellow-400 animate-pulse' :
                        cam.status === 'ERROR' ? 'bg-red-500' : 'bg-gray-300'
                      }`} />
                      <span className="text-xs text-gray-500">{cam.status}</span>
                      <span className="text-xs text-gray-400">• {cam.sample_fps} FPS</span>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {cameras.length > webcamCameras.length && (
              <details className="mt-3">
                <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
                  Show all cameras ({cameras.length})
                </summary>
                <div className="mt-2 space-y-1">
                  {cameras
                    .filter((c) => !webcamCameras.find((w) => w.id === c.id))
                    .map((cam) => (
                      <button
                        key={cam.id}
                        onClick={() => {
                          setSelectedCamera(cam);
                          setStreamState('IDLE');
                        }}
                        className={`w-full text-left px-3 py-2 rounded text-xs border transition ${
                          selectedCamera?.id === cam.id
                            ? 'bg-blue-50 border-blue-300 text-blue-700'
                            : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        {cam.camera_name} <span className="text-gray-400">({cam.stream_type})</span>
                      </button>
                    ))}
                </div>
              </details>
            )}
          </div>

          {/* Stream controls */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4" /> Stream Controls
            </h2>

            {/* Status indicator */}
            <div className="flex items-center gap-2 mb-4">
              <span className={`w-3 h-3 rounded-full inline-block ${selectedCamera ? statusColor(streamState) : 'bg-gray-200'}`} />
              <span className="text-sm font-medium text-gray-700">
                {selectedCamera ? statusLabel(streamState) : 'No camera selected'}
              </span>
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleStart}
                disabled={!selectedCamera || isRunning || loading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                {loading && streamState === 'CONNECTING' ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                Start Camera
              </button>
              <button
                onClick={handleStop}
                disabled={!selectedCamera || !isRunning || loading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                <Square className="w-4 h-4" />
                Stop Camera
              </button>
            </div>

            {/* Live status detail */}
            {statusDetail && (
              <div className="mt-3 p-3 bg-gray-50 rounded text-xs space-y-1 text-gray-600">
                <div className="flex justify-between">
                  <span>Stream worker</span>
                  <span className={statusDetail.is_streaming ? 'text-green-600 font-medium' : 'text-gray-400'}>
                    {statusDetail.is_streaming ? 'Running' : 'Stopped'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>AI pipeline</span>
                  <span className={statusDetail.is_pipeline_active ? 'text-green-600 font-medium' : 'text-gray-400'}>
                    {statusDetail.is_pipeline_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                {statusDetail.last_frame_at && (
                  <div className="flex justify-between">
                    <span>Last frame</span>
                    <span>{new Date(statusDetail.last_frame_at).toLocaleTimeString()}</span>
                  </div>
                )}
                {statusDetail.last_error && (
                  <div className="text-red-600 mt-1">
                    Error: {statusDetail.last_error}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* How to use */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <Info className="w-4 h-4" /> Demo Workflow
            </h2>
            <ol className="text-xs text-gray-600 space-y-2 list-decimal list-inside">
              <li>Register a webcam with device index <code className="bg-gray-100 px-1 rounded">0</code></li>
              <li>Enrol a test participant via <strong>Case Management → Reference Images</strong></li>
              <li>Click <strong>Start Camera</strong> and watch the live feed appear</li>
              <li>Have the enrolled participant appear on camera</li>
              <li>Check <strong>Review Dashboard</strong> for candidate match events</li>
              <li>Confirm or dismiss the match (human review required)</li>
              <li>Click <strong>Stop Camera</strong> when done</li>
            </ol>
            <div className="mt-3 p-2 bg-blue-50 rounded text-xs text-blue-700">
              <strong>Tip:</strong> The AI pipeline samples at the configured FPS (default: 1 FPS).
              Green boxes = detected faces. Matches are routed to the Review Dashboard.
            </div>
          </div>
        </div>

        {/* Right: Live video feed (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          {/* Video frame */}
          <div className="bg-black rounded-lg border border-gray-800 overflow-hidden relative min-h-[360px] flex items-center justify-center">
            {selectedCamera && streamUrl && isRunning ? (
              <>
                {/* MJPEG feed via plain img — works across all browsers */}
                <img
                  key={imgKey}
                  src={streamUrl}
                  alt="Live camera feed"
                  className="w-full h-auto object-contain"
                  style={{ maxHeight: '480px' }}
                  onError={() => setStreamState('ERROR')}
                />
                {/* LIVE badge */}
                <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-red-600 text-white text-xs font-bold px-2 py-1 rounded">
                  <span className="w-2 h-2 rounded-full bg-white animate-pulse inline-block" />
                  LIVE
                </div>
                {/* Camera name */}
                <div className="absolute bottom-3 left-3 bg-black/60 text-white text-xs px-2 py-1 rounded">
                  {selectedCamera.camera_name}
                </div>
              </>
            ) : (
              <div className="text-center text-gray-500 p-8">
                {!selectedCamera ? (
                  <>
                    <WifiOff className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                    <p className="text-sm">Select a camera from the left panel</p>
                  </>
                ) : streamState === 'ERROR' ? (
                  <>
                    <XCircle className="w-12 h-12 mx-auto mb-3 text-red-500" />
                    <p className="text-sm text-red-400">Stream error</p>
                    <p className="text-xs mt-1">{statusDetail?.last_error || 'Unknown error'}</p>
                  </>
                ) : (
                  <>
                    <Camera className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                    <p className="text-sm">Camera ready — click Start Camera</p>
                    <p className="text-xs mt-1 text-gray-600">{selectedCamera.camera_name}</p>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Selected camera info */}
          {selectedCamera && (
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <Eye className="w-4 h-4" /> Camera Details
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                <div>
                  <div className="text-gray-400 uppercase tracking-wider font-medium">Name</div>
                  <div className="text-gray-800 mt-0.5 font-medium">{selectedCamera.camera_name}</div>
                </div>
                <div>
                  <div className="text-gray-400 uppercase tracking-wider font-medium">Type</div>
                  <div className="text-gray-800 mt-0.5">
                    <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-mono">
                      {selectedCamera.stream_type}
                    </span>
                  </div>
                </div>
                <div>
                  <div className="text-gray-400 uppercase tracking-wider font-medium">Sample Rate</div>
                  <div className="text-gray-800 mt-0.5">{selectedCamera.sample_fps} FPS</div>
                </div>
                <div>
                  <div className="text-gray-400 uppercase tracking-wider font-medium">Location</div>
                  <div className="text-gray-800 mt-0.5">{selectedCamera.location_name || 'N/A'}</div>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-500 flex items-center gap-4">
                <span className="flex items-center gap-1">
                  <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                  Face detection: MTCNN / YuNet
                </span>
                <span className="flex items-center gap-1">
                  <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                  Matching: SFace / FaceNet embeddings
                </span>
                <span className="flex items-center gap-1">
                  <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                  Review: Human confirmation required
                </span>
              </div>
            </div>
          )}

          {/* Live Candidate Matches */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                <Eye className="w-4 h-4 text-blue-600" />
                Live Candidate Matches ({candidateMatches.length})
              </h3>
              <a
                href="/review"
                className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
              >
                Review Queue →
              </a>
            </div>

            {candidateMatches.length === 0 ? (
              <div className="text-xs text-gray-500 py-4 text-center bg-gray-50 rounded border border-dashed border-gray-200">
                <Eye className="w-5 h-5 mx-auto text-gray-400 mb-1" />
                <span className="font-medium">No candidate matches on this feed yet</span>
                <p className="text-[11px] text-gray-400 mt-0.5">
                  Unenrolled participants are ignored without creating alerts. When an enrolled Missing or Wanted identity appears, candidate match cards will display here.
                </p>
              </div>
            ) : (
              <div className="space-y-2 mt-2">
                {candidateMatches.slice(0, 5).map((match) => (
                  <div key={match.id} className="p-3 border rounded-lg bg-gray-50 border-gray-200 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-gray-900">{match.case_number}</span>
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        match.category === 'WANTED' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'
                      }`}>
                        {match.category}
                      </span>
                    </div>
                    <div className="text-[11px] text-gray-600 flex justify-between">
                      <span>Similarity: <strong>{(match.similarity_score * 100).toFixed(1)}%</strong></span>
                      <span>Rank: #{match.rank || 1}</span>
                    </div>
                    <div className="text-[11px] text-gray-500 flex justify-between">
                      <span>Camera: {selectedCamera?.camera_name || 'Laptop Front Camera'}</span>
                      <span>{new Date(match.created_at).toLocaleTimeString()}</span>
                    </div>
                    <div className="pt-1 flex items-center justify-between border-t border-gray-200">
                      <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                        POSSIBLE MATCH — HUMAN VERIFICATION REQUIRED
                      </span>
                      <a
                        href="/review"
                        className="text-[11px] text-blue-600 hover:text-blue-800 font-medium underline"
                      >
                        Verify →
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-3 pt-3 border-t border-gray-100 flex gap-2 flex-wrap">
              <a
                href="/review"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 transition"
              >
                <Eye className="w-3.5 h-3.5" /> Full Review Dashboard
              </a>
              <a
                href="/analytics/cameras"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded hover:bg-gray-200 transition"
              >
                <Activity className="w-3.5 h-3.5" /> Camera Analytics
              </a>
              <a
                href="/admin/cameras"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded hover:bg-gray-200 transition"
              >
                <Camera className="w-3.5 h-3.5" /> Camera Registry
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Register webcam modal */}
      {showRegister && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
            <div className="p-5 border-b border-gray-200">
              <h2 className="text-base font-semibold text-gray-900">Register Laptop Webcam</h2>
              <p className="text-xs text-gray-500 mt-1">
                Uses device index <code className="bg-gray-100 px-1 rounded">0</code> for the built-in front camera.
                Change to <code>1</code> for a secondary camera.
              </p>
            </div>
            <form onSubmit={handleRegister} className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Camera Name</label>
                <input
                  type="text"
                  value={registerForm.camera_name}
                  onChange={(e) => setRegisterForm({ ...registerForm, camera_name: e.target.value })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Department</label>
                <select
                  value={registerForm.department_id}
                  onChange={(e) => setRegisterForm({ ...registerForm, department_id: e.target.value })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="">Select department…</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>{d.department_name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Device Index</label>
                <input
                  type="text"
                  value={registerForm.stream_url}
                  onChange={(e) => setRegisterForm({ ...registerForm, stream_url: e.target.value })}
                  placeholder="0"
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-400 mt-1">
                  0 = built-in front camera, 1 = secondary USB camera
                </p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Sample Rate (FPS)</label>
                <input
                  type="number"
                  min="0.1"
                  max="10"
                  step="0.5"
                  value={registerForm.sample_fps}
                  onChange={(e) => setRegisterForm({ ...registerForm, sample_fps: parseFloat(e.target.value) })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Location Description</label>
                <input
                  type="text"
                  value={registerForm.location_name}
                  onChange={(e) => setRegisterForm({ ...registerForm, location_name: e.target.value })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowRegister(false)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={registering}
                  className="px-4 py-2 text-sm bg-blue-600 text-white font-medium rounded hover:bg-blue-700 disabled:opacity-50 transition"
                >
                  {registering ? 'Registering…' : 'Register Camera'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
