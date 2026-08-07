"use client";

import { useState, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { DocumentUploadSchema } from "@/lib/validators";

interface UploadDropzoneProps {
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
}

export function UploadDropzone({ onUpload, disabled }: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(async (file: File) => {
    setError(null);

    const validation = DocumentUploadSchema.safeParse({
      filename: file.name,
      fileType: file.type,
      size: file.size,
    });

    if (!validation.success) {
      setError(validation.error.issues[0].message);
      return;
    }

    setUploading(true);
    try {
      await onUpload(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [onUpload]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleClick = () => inputRef.current?.click();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  };

  return (
    <div>
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
        className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
          isDragging
            ? "border-amber bg-amber/5"
            : "border-border hover:border-amber/50"
        } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.docx,.txt,.md,.csv,.png,.jpg,.jpeg,.tiff,.bmp,.webp"
          onChange={handleChange}
          disabled={disabled || uploading}
        />

        {uploading ? (
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 border-2 border-amber border-t-transparent rounded-full animate-spin" />
            <p className="text-ink font-medium">Uploading...</p>
          </div>
        ) : (
          <>
            <p className="text-ink font-medium mb-1">
              Drop your documents here
            </p>
            <p className="text-muted-foreground text-sm mb-4">
              PDF, DOCX, TXT, or images — up to 25MB
            </p>
            <Button variant="outline" size="sm" type="button">
              Browse files
            </Button>
          </>
        )}
      </div>

      {error && (
        <p className="mt-2 text-rust text-sm">{error}</p>
      )}
    </div>
  );
}
