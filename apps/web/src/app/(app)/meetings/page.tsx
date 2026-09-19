"use client";

import { useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { withProject } from "@/lib/api/client";
import { useProjectStore } from "@/stores/project";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { MeetingAnalysisCard } from "@/components/features/meetings";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { MeetingAnalysis } from "@/lib/types";

export default function MeetingsPage() {
  const supabaseRef = useRef(createClient());
  const supabase = supabaseRef.current;
  const { activeProjectId } = useProjectStore();
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<MeetingAnalysis | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordingRef = useRef(false);
  const chunksRef = useRef<Blob[]>([]);
  const mimeTypeRef = useRef<string>("audio/webm");
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startRecording = async () => {
    setError(null);
    setAnalysis(null);
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
      setError("Could not start recording — allow tab/screen sharing with audio.");
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
    setProcessing(true);
    setError(null);
    try {
      const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current });
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Not authenticated");
      const ext = mimeTypeRef.current.includes("mp4") ? "m4a" : "webm";
      const formData = new FormData();
      formData.append("file", new File([blob], `meeting.${ext}`, { type: mimeTypeRef.current }));
      let res: Response;
      try {
        res = await fetch(withProject("/meetings/analyze", activeProjectId), {
          method: "POST",
          headers: { Authorization: `Bearer ${session.access_token}` },
          body: formData,
        });
      } catch {
        throw new Error("Cannot reach the server. Check that the backend is running and try again.");
      }
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || "Analysis failed");
      }
      setAnalysis((await res.json()) as MeetingAnalysis);
    } catch (e: any) {
      setError(e.message || "Failed to analyze meeting");
    } finally {
      setProcessing(false);
    }
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
