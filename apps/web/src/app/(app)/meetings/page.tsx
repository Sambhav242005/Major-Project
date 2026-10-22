"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import type { SystemStatus } from "@/lib/system-status";
import { useAuth } from "@/hooks/useAuth";
import { useMeetings } from "@/hooks/useMeetings";
import { useProjectStore } from "@/stores/project";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { MeetingAnalysisCard } from "@/components/features/meetings";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function MeetingsPage() {
  const { activeProjectId } = useProjectStore();
  const { token } = useAuth();
  const { analysis, processing, error, analyzeMeeting, history, historyLoading, historyError, refreshHistory, selectAnalysis } = useMeetings({ token, projectId: activeProjectId });
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const [recordingAvailable, setRecordingAvailable] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordingRef = useRef(false);
  const chunksRef = useRef<Blob[]>([]);
  const mimeTypeRef = useRef<string>("audio/webm");
  const streamRef = useRef<MediaStream | null>(null);
  const displayRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let active = true;
    void apiFetch<SystemStatus>("/system/status", { token }).then((status) => {
      if (active) { setRecordingAvailable(status.capabilities.meetings_recording); setRecordingError(null); }
    }).catch(() => { if (active) setRecordingError("Could not check transcription availability. Reload to retry."); });
    return () => {
      active = false;
      recordingRef.current = false;
      if (recorderRef.current) recorderRef.current.onstop = null;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      displayRef.current?.getTracks().forEach((track) => track.stop());
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [token]);

  const startRecording = async () => {
    setRecordingError(null);
    try {
      if (!activeProjectId) throw new Error("Select a project before recording.");
      if (!navigator.mediaDevices || typeof MediaRecorder === "undefined") throw new Error("Recording requires HTTPS and a browser that supports audio capture. You can upload an audio file instead.");
      const display = navigator.mediaDevices.getDisplayMedia
        ? await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true })
        : await navigator.mediaDevices.getUserMedia({ audio: true });
      displayRef.current = display;
      let audioTrack = display.getAudioTracks()[0];
      if (!audioTrack) {
        const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioTrack = mic.getAudioTracks()[0];
        display.getTracks().forEach((t) => t.stop());
      }
      const audioStream = new MediaStream(audioTrack ? [audioTrack] : []);
      streamRef.current = audioStream;
      chunksRef.current = [];
      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]
        .find((m) => MediaRecorder.isTypeSupported(m));
      mimeTypeRef.current = mimeType || "audio/webm";
      const recorder = new MediaRecorder(audioStream, mimeType ? { mimeType } : undefined);
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = handleStop;
      recorder.start(1000);
      recorderRef.current = recorder;
      recordingRef.current = true;
      setRecording(true);
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
      const stopOnEnd = () => { if (recordingRef.current) stopRecording(); };
      display.getVideoTracks()[0]?.addEventListener("ended", stopOnEnd);
      display.getVideoTracks().forEach((t) => { if (t !== display.getAudioTracks()[0]) t.enabled = false; });
    } catch (error) {
      displayRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current?.getTracks().forEach((track) => track.stop());
      setRecordingError(error instanceof Error ? error.message : "Recording could not start. Check microphone and screen-sharing permission.");
    }
  };

  const stopRecording = () => {
    recordingRef.current = false;
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    displayRef.current?.getTracks().forEach((t) => t.stop());
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    setRecording(false);
  };

  const handleStop = async () => {
    try {
      const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current });
      const ext = mimeTypeRef.current.includes("mp4") ? "m4a" : "webm";
      await analyzeMeeting(new File([blob], `meeting.${ext}`, { type: mimeTypeRef.current }));
    } catch { /* hook exposes the user-facing error */ }
  };

  const formatTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <DashboardHeader title="Meetings" showBack backHref="/dashboard" />
      <main className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        <Card className="bg-app-card border border-app-border">
          <CardHeader>
            <CardTitle className="font-display text-lg">Meeting Recorder</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-app-muted">
              Record or upload meeting audio for transcription and analysis. Audio is sent to Google Web Speech for transcription; the transcript is sent to the configured generation provider. Obtain participants’ permission first.
            </p>
            {!recordingAvailable && <p className="text-sm text-amber-400">Audio analysis is unavailable until transcription dependencies are ready on the server.</p>}
            {(error || recordingError) && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {recordingError || error}
              </div>
            )}
            <div className="flex items-center gap-4">
              {!recording ? (
                <Button onClick={startRecording} disabled={processing || !recordingAvailable || !activeProjectId}>
                  {processing ? "Analyzing..." : "Start recording"}
                </Button>
              ) : (
                <>
                  <Button onClick={stopRecording} variant="destructive"
                    className="bg-rust/20 text-app-text border border-rust/40 hover:bg-rust/30">
                    Stop &amp; analyze
                  </Button>
                  <span className="text-sm font-mono text-app-muted animate-pulse">
                    ● {formatTime(elapsed)}
                  </span>
                </>
              )}
            </div>
            <label className="block text-sm text-app-muted">Upload audio
              <input className="block mt-2 text-xs" type="file" accept="audio/*" disabled={recording || processing || !recordingAvailable || !activeProjectId} onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) { setRecordingError(null); void analyzeMeeting(file).catch(() => undefined); }
                event.target.value = "";
              }} />
            </label>
          </CardContent>
        </Card>

        <section className="glow-card p-4 space-y-3">
          <div className="flex justify-between items-center"><h2 className="text-sm font-medium">Saved meeting analyses</h2><button className="text-xs underline" disabled={historyLoading} onClick={() => { void refreshHistory(); }}>Refresh history</button></div>
          {historyError && <p role="alert" className="text-sm text-red-400">{historyError}</p>}
          {historyLoading ? <p className="text-sm text-app-muted">Loading saved analyses...</p> : history.length === 0 ? <p className="text-sm text-app-muted">No saved analyses in this project yet.</p> : <ul className="space-y-2">
            {history.map((item, index) => <li key={item.id ?? index}><button className="w-full text-left rounded border border-app-border px-3 py-2 text-sm hover:bg-app-surface" disabled={processing || recording} onClick={() => selectAnalysis(item)}>
              <span className="block">{item.filename || "Meeting audio"}</span><span className="text-xs text-app-muted">{item.created_at ? new Date(item.created_at).toLocaleString() : "Saved analysis"}</span>
            </button></li>)}
          </ul>}
        </section>
        {analysis && <section aria-label="Selected meeting analysis"><MeetingAnalysisCard analysis={analysis} /></section>}
      </main>
    </div>
  );
}
