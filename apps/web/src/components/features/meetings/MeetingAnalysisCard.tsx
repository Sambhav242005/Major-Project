"use client";

import { FileText, CheckCircle, AlertCircle, Clock } from "lucide-react";
import type { MeetingAnalysis } from "@/lib/types";

const SENTIMENT_COLORS: Record<string, string> = {
  positive: "text-emerald-400",
  negative: "text-red-400",
  neutral: "text-app-muted",
  mixed: "text-amber-400",
};

interface MeetingAnalysisCardProps {
  analysis: MeetingAnalysis;
}

export function MeetingAnalysisCard({ analysis }: MeetingAnalysisCardProps) {
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="glow-card p-4">
        <h3 className="text-sm font-medium text-app-text mb-2 flex items-center gap-2">
          <FileText size={14} className="text-sky-400" />
          Summary
        </h3>
        <p className="text-xs text-app-muted leading-relaxed">{analysis.summary}</p>
      </div>

      {/* Sentiment */}
      <div className="glow-card p-4">
        <h3 className="text-sm font-medium text-app-text mb-2 flex items-center gap-2">
          <AlertCircle size={14} className="text-sky-400" />
          Sentiment
        </h3>
        <span className={`text-xs font-medium ${SENTIMENT_COLORS[analysis.sentiment] || "text-app-muted"}`}>
          {analysis.sentiment}
        </span>
        {analysis.sentiment_reason && (
          <p className="text-[11px] text-app-muted mt-1">{analysis.sentiment_reason}</p>
        )}
      </div>

      {/* Key Points */}
      {analysis.key_points.length > 0 && (
        <div className="glow-card p-4">
          <h3 className="text-sm font-medium text-app-text mb-2 flex items-center gap-2">
            <CheckCircle size={14} className="text-sky-400" />
            Key Points
          </h3>
          <ul className="space-y-1.5">
            {analysis.key_points.map((point, i) => (
              <li key={i} className="text-xs text-app-muted flex items-start gap-2">
                <span className="text-sky-400 mt-0.5">•</span>
                {point}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Action Items */}
      {analysis.action_items.length > 0 && (
        <div className="glow-card p-4">
          <h3 className="text-sm font-medium text-app-text mb-2 flex items-center gap-2">
            <Clock size={14} className="text-sky-400" />
            Action Items
          </h3>
          <ul className="space-y-1.5">
            {analysis.action_items.map((item, i) => (
              <li key={i} className="text-xs text-app-muted flex items-start gap-2">
                <span className="text-amber-400 mt-0.5">▸</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Transcript */}
      {analysis.transcript && (
        <div className="glow-card p-4">
          <h3 className="text-sm font-medium text-app-text mb-2">Transcript</h3>
          <div className="max-h-60 overflow-y-auto">
            <p className="text-xs text-app-muted leading-relaxed whitespace-pre-wrap">
              {analysis.transcript}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
