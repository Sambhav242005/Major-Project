"use client";

import { useCallback, useState } from "react";
import { Upload, FileText, Loader2 } from "lucide-react";
import { ALLOWED_FILE_TYPES, MAX_FILE_SIZE } from "@/lib/types";

interface DocumentUploadCardProps {
  onUpload: (files: File[]) => Promise<void>;
  isUploading?: boolean;
}

export function DocumentUploadCard({ onUpload, isUploading }: DocumentUploadCardProps) {
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return;
      const valid = Array.from(files).filter(
        (f) => f.size <= MAX_FILE_SIZE && (ALLOWED_FILE_TYPES as readonly string[]).includes(f.type)
      );
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
          PDF, TXT, MD, DOCX, CSV • Max {Math.round(MAX_FILE_SIZE / 1024 / 1024)}MB
        </p>
      </div>
    </div>
  );
}
