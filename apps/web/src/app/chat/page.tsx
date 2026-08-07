"use client";

import { useState } from "react";
import Link from "next/link";

export default function ChatPage() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setMessage("");
    // Backend not connected — show placeholder response
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Chat requires a connected backend and knowledge base. Upload documents first to enable Q&A." },
      ]);
    }, 500);
  };

  return (
    <div className="min-h-screen bg-paper flex flex-col">
      <header className="border-b border-slate/20 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm text-slate hover:text-ink transition-colors">
              ← Dashboard
            </Link>
            <h1 className="font-display text-xl font-semibold text-ink">
              Chat
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/documents" className="text-sm text-slate hover:text-ink transition-colors">
              Documents
            </Link>
            <Link href="/graph" className="text-sm text-slate hover:text-ink transition-colors">
              Graph
            </Link>
            <form action="/auth/signout" method="post">
              <button type="submit" className="text-sm text-rust hover:underline">
                Sign out
              </button>
            </form>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-6 flex flex-col">
        <div className="flex-1 overflow-y-auto mb-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-20 text-slate">
              <p className="text-lg mb-2">Ask questions about your documents</p>
              <p className="text-sm">Upload documents in the Document Library to start building your knowledge base</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                  msg.role === "user"
                    ? "bg-ink text-paper"
                    : "bg-white border border-slate/20 text-ink"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
        </div>

        <form onSubmit={handleSend} className="flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Ask a question about your documents..."
            className="flex-1 px-4 py-2 border border-slate/30 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber bg-white text-ink"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-ink text-paper rounded-lg hover:bg-ink/90 transition-colors"
          >
            Send
          </button>
        </form>
      </main>
    </div>
  );
}
