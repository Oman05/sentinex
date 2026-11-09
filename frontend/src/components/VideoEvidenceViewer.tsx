import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, RotateCcw, ShieldAlert, Film, Lock, AlertTriangle, Download } from 'lucide-react';
import type { EvidenceItem } from '../types/evidence';
import { downloadEvidenceContent } from '../services/evidenceApi';

interface VideoEvidenceViewerProps {
  item: EvidenceItem;
  onDownloadRequested?: (reason: string) => void;
}

export const VideoEvidenceViewer: React.FC<VideoEvidenceViewerProps> = ({ item, onDownloadRequested }) => {
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [reasonPromptOpen, setReasonPromptOpen] = useState(false);
  const [downloadReason, setDownloadReason] = useState('');
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Load authenticated video stream via secure blob URL
  const loadVideo = async (reason: string) => {
    try {
      setLoading(true);
      setError(null);
      const blob = await downloadEvidenceContent(item.evidence_id, reason);
      const url = URL.createObjectURL(blob);
      setVideoUrl(url);
      setReasonPromptOpen(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to authenticate video access');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // If not loaded, require explicit view justification or auto-request with default reason
    loadVideo('Authorized officer video playback preview');
    return () => {
      if (videoUrl) {
        URL.revokeObjectURL(videoUrl);
      }
    };
  }, [item.evidence_id]);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
      setDuration(videoRef.current.duration || 0);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${mins}:${s < 10 ? '0' : ''}${s}`;
  };

  return (
    <div className="bg-gray-900 rounded-xl overflow-hidden border border-gray-800 shadow-xl text-white">
      {/* Header */}
      <div className="bg-gray-950 px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Film className="w-5 h-5 text-indigo-400" />
          <span className="font-semibold text-sm tracking-wide">AUTHORIZED VIDEO EVIDENCE VIEWER</span>
          <span className="bg-red-950 text-red-400 text-[10px] px-2 py-0.5 rounded font-bold border border-red-800 flex items-center gap-1">
            <Lock className="w-3 h-3" /> PROTECTED ACCESS
          </span>
        </div>
        <div className="text-xs text-gray-400 font-mono">
          ID: {item.evidence_id} | CAM: {item.camera_id ? `CAM-${item.camera_id}` : 'N/A'}
        </div>
      </div>

      {/* Video Viewport with overlay watermark */}
      <div className="relative aspect-video bg-black flex items-center justify-center select-none overflow-hidden">
        {loading && (
          <div className="flex flex-col items-center gap-2 text-gray-400 text-sm">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            <span>Authorizing and streaming encrypted evidence...</span>
          </div>
        )}

        {error && (
          <div className="p-6 text-center max-w-md">
            <AlertTriangle className="w-10 h-10 text-rose-500 mx-auto mb-2" />
            <div className="text-sm font-semibold text-rose-400">{error}</div>
            <p className="text-xs text-gray-400 mt-2">
              Raw CCTV video files cannot be accessed without proper authorization and departmental credentials.
            </p>
          </div>
        )}

        {videoUrl && !loading && (
          <>
            <video
              ref={videoRef}
              src={videoUrl}
              className="w-full h-full object-contain"
              onTimeUpdate={handleTimeUpdate}
              onEnded={() => setIsPlaying(false)}
              controlsList="nodownload noplaybackrate"
              disablePictureInPicture
              onContextMenu={(e) => e.preventDefault()}
            />
            {/* Transparent Security Watermark */}
            <div className="absolute inset-0 pointer-events-none flex flex-col justify-between p-4 opacity-25">
              <div className="text-xs font-mono font-bold tracking-widest text-white">
                SENTINEX SECURE AUDIT • {item.evidence_id}
              </div>
              <div className="text-center font-mono text-sm tracking-widest text-white uppercase">
                RESTRICTED LAW ENFORCEMENT EVIDENCE — REPRODUCTION PROHIBITED
              </div>
              <div className="text-right text-xs font-mono text-white">
                CAPTURE: {item.captured_at ? new Date(item.captured_at).toISOString() : 'RECORDED'}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Timeline Controls */}
      <div className="p-4 bg-gray-950 border-t border-gray-800 space-y-3">
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            disabled={!videoUrl || loading}
            className="p-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-lg transition-colors"
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>
          <button
            onClick={() => {
              if (videoRef.current) videoRef.current.currentTime = 0;
            }}
            disabled={!videoUrl}
            className="p-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors"
            title="Restart"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {/* Time Scrubber */}
          <div className="flex-1 flex items-center gap-3">
            <span className="font-mono text-xs text-gray-400 min-w-[40px]">{formatTime(currentTime)}</span>
            <input
              type="range"
              min="0"
              max={duration || 100}
              value={currentTime}
              onChange={handleSeek}
              disabled={!videoUrl}
              className="flex-1 h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <span className="font-mono text-xs text-gray-400 min-w-[40px]">{formatTime(duration)}</span>
          </div>

          {/* Authorized Download */}
          <button
            onClick={() => setReasonPromptOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-xs font-medium rounded-lg text-gray-300 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Export Clip
          </button>
        </div>

        {/* Clip Provenance Window info */}
        <div className="flex items-center justify-between text-xs text-gray-400 pt-2 border-t border-gray-800/80">
          <div>
            Method: <strong className="text-gray-300">{item.clip_generation_method || 'AUTO_WINDOW'}</strong>
          </div>
          <div>
            Duration: <strong className="text-gray-300">{item.clip_duration_seconds ? `${item.clip_duration_seconds.toFixed(1)}s` : 'Configured Window'}</strong>
          </div>
          <div className="font-mono text-[11px] text-gray-500">
            {item.clip_start_time ? new Date(item.clip_start_time).toLocaleTimeString() : ''} &rarr;{' '}
            {item.clip_end_time ? new Date(item.clip_end_time).toLocaleTimeString() : ''}
          </div>
        </div>
      </div>

      {/* Export / Download Reason Modal */}
      {reasonPromptOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-md w-full shadow-2xl">
            <h4 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-amber-500" />
              Authorized Evidence Export Protocol
            </h4>
            <p className="text-xs text-gray-400 mb-4">
              All video evidence downloads are logged into the permanent system audit trail. An official investigative rationale is mandatory.
            </p>
            <textarea
              value={downloadReason}
              onChange={(e) => setDownloadReason(e.target.value)}
              placeholder="State investigation purpose, case reference, or court subpoena order..."
              className="w-full bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 mb-4 h-24"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setReasonPromptOpen(false)}
                className="px-3 py-1.5 text-xs text-gray-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (downloadReason.trim().length >= 5) {
                    if (onDownloadRequested) onDownloadRequested(downloadReason);
                    loadVideo(downloadReason);
                    setReasonPromptOpen(false);
                  }
                }}
                disabled={downloadReason.trim().length < 5}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-xs font-semibold rounded-lg text-white"
              >
                Confirm &amp; Export
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
