"use client";

import { Mic, Square, Upload, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface MeetingRecorderProps {
  isRecording: boolean;
  recordingBlob: Blob | null;
  isUploading: boolean;
  onToggleRecording: () => void;
  onUploadRecording: () => void;
}

export function MeetingRecorder({
  isRecording,
  recordingBlob,
  isUploading,
  onToggleRecording,
  onUploadRecording,
}: MeetingRecorderProps) {
  return (
    <div className="glow-card p-6 text-center">
      <Mic size={48} className="mx-auto mb-4 text-app-muted" />
      <h3 className="text-sm font-medium text-app-text mb-2">Record Meeting</h3>
      <p className="text-xs text-app-muted mb-4">
        Record audio from your meeting for transcription and analysis
      </p>
      <div className="flex items-center justify-center gap-2">
        <Button
          variant={isRecording ? "destructive" : "default"}
          size="sm"
          className="text-xs"
          onClick={onToggleRecording}
        >
          {isRecording ? (
            <>
              <Square size={12} className="mr-1" />
              Stop Recording
            </>
          ) : (
            <>
              <Mic size={12} className="mr-1" />
              Start Recording
            </>
          )}
        </Button>
        {recordingBlob && !isRecording && (
          <Button
            variant="outline"
            size="sm"
            className="text-xs"
            onClick={onUploadRecording}
            disabled={isUploading}
          >
            {isUploading ? (
              <Loader2 size={12} className="mr-1 animate-spin" />
            ) : (
              <Upload size={12} className="mr-1" />
            )}
            Upload Recording
          </Button>
        )}
      </div>
    </div>
  );
}
