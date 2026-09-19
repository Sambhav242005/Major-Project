"use client";

import { useRef, useState } from "react";
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
  const { analysis, processing, error, analyzeMeeting } = useMeetings({ token, projectId: activeProjectId });
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordingRef = useRef(false);
  const chunksRef = useRef<Blob[]>([]);
  const mimeTypeRef = useRef<string>("audio/webm");
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startRecording = async () => {
    try {
      const display = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
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
    } catch {
      // Browser permission errors are surfaced by the recorder UI.
    }
  };

  const stopRecording = () => {
    recordingRef.current = false;
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
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
              Record audio from your meeting for transcription and analysis.
            </p>
            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {error}
              </div>
            )}
            <div className="flex items-center gap-4">
              {!recording ? (
                <Button onClick={startRecording} disabled={processing}>
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
          </CardContent>
        </Card>

        {analysis && <MeetingAnalysisCard analysis={analysis} />}
      </main>
    </div>
  );
}
