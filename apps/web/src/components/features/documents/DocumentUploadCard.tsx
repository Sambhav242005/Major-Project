"use client";

import { useCallback, useState } from "react";
import { Upload, FileText, Loader2 } from "lucide-react";
import { ACCEPTED_FORMATS_MESSAGE, ALLOWED_FILE_TYPES, IMAGE_MAX_FILE_SIZE, MAX_FILE_SIZE, NOT_YET_SUPPORTED_MESSAGE, sizeLimitMessage } from "@/lib/types";

function rejectionReason(file: File): string | null {
  if (!ALLOWED_FILE_TYPES.includes(file.type as (typeof ALLOWED_FILE_TYPES)[number])) {
    if (file.type.startsWith("audio/")) return NOT_YET_SUPPORTED_MESSAGE;
    if (file.type.startsWith("video/")) return NOT_YET_SUPPORTED_MESSAGE;
    return `${file.name}: unknown file type. ${ACCEPTED_FORMATS_MESSAGE}`;
  }
  if (file.size > (file.type.startsWith("image/") ? IMAGE_MAX_FILE_SIZE : MAX_FILE_SIZE)) {
    return sizeLimitMessage(file.type, file.name);
  }
  return null;
}

interface DocumentUploadCardProps {
  onUpload: (files: File[]) => Promise<void>;
  isUploading?: boolean;
}

export function DocumentUploadCard({ onUpload, isUploading }: DocumentUploadCardProps) {
  const [dragOver, setDragOver] = useState(false);
  const [rejections, setRejections] = useState<string[]>([]);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return;
      const rejected: string[] = [];
      const valid: File[] = [];
      Array.from(files).forEach((file) => {
        const reason = rejectionReason(file);
        if (reason) rejected.push(reason);
        else valid.push(file);
      });
      setRejections(rejected);
      if (valid.length > 0) onUpload(valid);
    },
    [onUpload]
  );

  return (
    <div
      className={`glow-card p-6 border-2 border-dashed transition-colors ${
        dragOver ? "border-sky-400 bg-sky-400/5" : "border-app-border"
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      <div className="text-center">
        {isUploading ? (
          <Loader2 size={32} className="mx-auto mb-3 text-sky-400 animate-spin" />
        ) : (
          <Upload size={32} className="mx-auto mb-3 text-app-muted" />
        )}
        <p className="text-sm text-app-text">
          {isUploading ? "Uploading..." : "Drag & drop files here"}
        </p>
        <p className="text-xs text-app-muted mt-1">or</p>
        <label className="mt-2 inline-block">
          <span className="glow-button text-xs px-3 py-1.5 cursor-pointer inline-flex items-center gap-1.5">
            <FileText size={12} />
            Browse Files
          </span>
          <input
            type="file"
            className="hidden"
            multiple
            accept={ALLOWED_FILE_TYPES.join(",")}
            onChange={(e) => handleFiles(e.target.files)}
          />
        </label>
        <p className="text-[10px] text-app-muted mt-2">
          Documents, images, WAV/MP3/FLAC audio, MP4/WebM video &bull; up to {Math.round(MAX_FILE_SIZE / 1024 / 1024)}MB ({Math.round(IMAGE_MAX_FILE_SIZE / 1024 / 1024)}MB images)
        </p>
        <p className="text-[10px] text-app-muted">
          Audio/video requires configured Whisper and vision models.
        </p>
        {rejections.length > 0 && (
          <div className="mt-2 text-rust text-xs" role="alert">
            {rejections.slice(0, 3).map((reason) => (
              <p key={reason}>{reason}</p>
            ))}
            {rejections.length > 3 && <p>+{rejections.length - 3} more rejected</p>}
          </div>
        )}
      </div>
    </div>
  );
}
