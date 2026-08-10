"use client";

import { useState } from "react";
import Link from "next/link";
import { PublicHeader } from "@/components/public-header";

export default function ContactPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="min-h-screen bg-app-bg">
      <PublicHeader />

      <main className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="font-display text-4xl font-bold text-app-text mb-6">Contact Us</h1>
        <p className="text-app-muted text-lg mb-10">
          Have questions, feedback, or want to collaborate? We&apos;d love to hear from you.
        </p>

        <div className="glow-card bg-app-card rounded-lg border border-app-border p-8 mb-8">
          <h2 className="font-display text-xl font-semibold text-app-text mb-4">Get in Touch</h2>
          {submitted ? (
            <div className="text-center py-8">
              <p className="text-verified font-medium text-lg mb-2">Message sent!</p>
              <p className="text-app-muted text-sm">Thank you for reaching out. We&apos;ll get back to you soon.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="name" className="text-sm font-medium text-app-text block mb-1">Name</label>
                <input
                  id="name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="Your name"
                  className="w-full px-4 py-2 border border-app-border-strong rounded-lg focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber bg-app-surface-alt text-app-text placeholder:text-slate-600"
                />
              </div>
              <div>
                <label htmlFor="email" className="text-sm font-medium text-app-text block mb-1">Email</label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="your@email.com"
                  className="w-full px-4 py-2 border border-app-border-strong rounded-lg focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber bg-app-surface-alt text-app-text placeholder:text-slate-600"
                />
              </div>
              <div>
                <label htmlFor="message" className="text-sm font-medium text-app-text block mb-1">Message</label>
                <textarea
                  id="message"
                  rows={5}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  required
                  placeholder="How can we help?"
                  className="w-full px-4 py-2 border border-app-border-strong rounded-lg focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber bg-app-surface-alt text-app-text placeholder:text-slate-600 resize-none"
                />
              </div>
              <button
                type="submit"
                className="px-6 py-2 bg-app-text text-app-bg font-medium rounded-lg hover:bg-app-card-hover transition-colors"
              >
                Send Message
              </button>
            </form>
          )}
        </div>

        <div className="glow-card bg-app-card rounded-lg border border-app-border p-8">
          <h2 className="font-display text-xl font-semibold text-app-text mb-4">Project Details</h2>
          <p className="text-app-muted text-sm mb-4">
            This is a college semester project demonstrating AI-powered knowledge graph construction
            from documents. The system uses modern NLP, vector search, and graph databases to
            transform unstructured text into navigable knowledge.
          </p>
          <p className="text-app-muted text-sm">
            Tech stack: Next.js, FastAPI, PostgreSQL, ChromaDB, NetworkX, LangGraph, spaCy, OpenAI.
          </p>
        </div>
      </main>

      <footer className="border-t border-app-border bg-app-card/50 mt-16">
        <div className="max-w-7xl mx-auto px-6 py-8 flex items-center justify-between">
          <p className="text-sm text-app-muted">
            &copy; 2026 AI Knowledge Graph Builder. Semester Project.
          </p>
          <div className="flex items-center gap-6">
            <Link href="/terms" className="text-sm text-app-muted hover:text-app-text transition-colors">
              Terms of Service
            </Link>
            <Link href="/" className="text-sm text-app-muted hover:text-app-text transition-colors">
              Home
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
