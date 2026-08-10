import Link from "next/link";
import { PublicHeader } from "@/components/public-header";

export default function DemoPage() {
  return (
    <div className="min-h-screen bg-app-bg">
      <PublicHeader />

      <main className="max-w-4xl mx-auto px-6 py-16">
        <h1 className="font-display text-4xl font-bold text-app-text mb-4">Try the Demo</h1>
        <p className="text-app-muted text-lg mb-12">
          Here&apos;s how to explore the AI Knowledge Graph Builder step by step.
        </p>

        <div className="space-y-8">
          {/* Step 1 */}
          <div className="glow-card bg-app-card rounded-lg border border-app-border p-8">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-amber-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="text-amber dark:text-amber font-bold">1</span>
              </div>
              <div>
                <h2 className="font-display text-xl font-semibold text-app-text mb-2">
                  Sign Up for Free
                </h2>
                <p className="text-app-muted mb-4">
                  Try the demo instantly — no account needed. Demo credentials are used automatically.
                </p>
                <form action="/auth/demo-login" method="post">
                  <button
                    type="submit"
                    className="inline-block px-6 py-2 bg-sky-500/20 text-sky-600 dark:text-sky-400 font-medium rounded-lg hover:bg-sky-500/30 transition-colors text-sm"
                  >
                    Enter Demo
                  </button>
                </form>
              </div>
            </div>
          </div>

          {/* Step 2 */}
          <div className="glow-card bg-app-card rounded-lg border border-app-border p-8">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-amber-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="text-amber dark:text-amber font-bold">2</span>
              </div>
              <div>
                <h2 className="font-display text-xl font-semibold text-app-text mb-2">
                  Upload Documents
                </h2>
                <p className="text-app-muted mb-4">
                  Go to the <strong>Document Library</strong> and drag & drop your files. Supported formats:
                </p>
                <div className="flex flex-wrap gap-2 mb-4">
                  {["PDF", "DOCX", "TXT", "Markdown", "CSV", "PNG", "JPEG", "TIFF", "BMP", "WebP"].map((fmt) => (
                    <span key={fmt} className="px-3 py-1 bg-app-surface rounded text-sm text-app-text">
                      {fmt}
                    </span>
                  ))}
                </div>
                <p className="text-app-muted text-sm">
                  Files are parsed, chunked, embedded into vectors, and entities are extracted automatically.
                </p>
              </div>
            </div>
          </div>

          {/* Step 3 */}
          <div className="glow-card bg-app-card rounded-lg border border-app-border p-8">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-amber-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="text-amber dark:text-amber font-bold">3</span>
              </div>
              <div>
                <h2 className="font-display text-xl font-semibold text-app-text mb-2">
                  Watch the Knowledge Graph Build
                </h2>
                <p className="text-app-muted mb-4">
                  As documents are processed, the system extracts entities (people, organizations,
                  locations, concepts) and maps relationships between them. Check the <strong>Dashboard</strong> for
                  real-time pipeline status.
                </p>
                <Link
                  href="/dashboard"
                  className="inline-block px-6 py-2 border border-app-border-strong text-app-text font-medium rounded-lg hover:bg-app-card-hover transition-colors text-sm"
                >
                  Go to Dashboard
                </Link>
              </div>
            </div>
          </div>

          {/* Step 4 */}
          <div className="glow-card bg-app-card rounded-lg border border-app-border p-8">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-amber-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="text-amber dark:text-amber font-bold">4</span>
              </div>
              <div>
                <h2 className="font-display text-xl font-semibold text-app-text mb-2">
                  Explore the Graph
                </h2>
                <p className="text-app-muted mb-4">
                  Open the <strong>Knowledge Graph Explorer</strong> to visually navigate entity
                  relationships. Search for entities, adjust traversal depth, and click nodes to
                  see connected chunks and source documents.
                </p>
                <Link
                  href="/graph"
                  className="inline-block px-6 py-2 border border-app-border-strong text-app-text font-medium rounded-lg hover:bg-app-card-hover transition-colors text-sm"
                >
                  Open Graph Explorer
                </Link>
              </div>
            </div>
          </div>

          {/* Step 5 */}
          <div className="glow-card bg-app-card rounded-lg border border-app-border p-8">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-amber-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="text-amber dark:text-amber font-bold">5</span>
              </div>
              <div>
                <h2 className="font-display text-xl font-semibold text-app-text mb-2">
                  Ask Questions
                </h2>
                <p className="text-app-muted mb-4">
                  Use the <strong>Chat</strong> to ask natural language questions about your documents.
                  The system retrieves relevant chunks using vector search + graph expansion and
                  generates answers with citations.
                </p>
                <Link
                  href="/chat"
                  className="inline-block px-6 py-2 border border-app-border-strong text-app-text font-medium rounded-lg hover:bg-app-card-hover transition-colors text-sm"
                >
                  Start Chatting
                </Link>
              </div>
            </div>
          </div>

          {/* Step 6 */}
          <div className="glow-card bg-app-card rounded-lg border border-app-border p-8">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-amber-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="text-amber dark:text-amber font-bold">6</span>
              </div>
              <div>
                <h2 className="font-display text-xl font-semibold text-app-text mb-2">
                  Run AI Agents
                </h2>
                <p className="text-app-muted mb-4">
                  Create specialized AI agents for deeper analysis: summarizers, extractors,
                  Q&A agents, and reviewers. Each agent runs with full trace visibility.
                </p>
                <Link
                  href="/agents"
                  className="inline-block px-6 py-2 border border-app-border-strong text-app-text font-medium rounded-lg hover:bg-app-card-hover transition-colors text-sm"
                >
                  Manage Agents
                </Link>
              </div>
            </div>
          </div>

          {/* Step 7 */}
          <div className="glow-card bg-app-card rounded-lg border border-app-border p-8">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-amber-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="text-amber dark:text-amber font-bold">7</span>
              </div>
              <div>
                <h2 className="font-display text-xl font-semibold text-app-text mb-2">
                  Connect External Tools
                </h2>
                <p className="text-app-muted mb-4">
                  Use <strong>MCP Connections</strong> to share your knowledge base with external tools
                  (sender mode) or pull data from other sources (receiver mode). Google Meet
                  transcript sync is also available.
                </p>
                <Link
                  href="/mcp"
                  className="inline-block px-6 py-2 border border-app-border-strong text-app-text font-medium rounded-lg hover:bg-app-card-hover transition-colors text-sm"
                >
                  Configure MCP
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="text-center mt-16 py-12 border-t border-app-border">
          <h2 className="font-display text-2xl font-semibold text-app-text mb-4">
            Ready to Get Started?
          </h2>
          <form action="/auth/demo-login" method="post">
            <button
              type="submit"
              className="px-8 py-3 bg-sky-500/20 text-sky-600 dark:text-sky-400 font-medium rounded-lg hover:bg-sky-500/30 transition-colors text-lg"
            >
              Enter Demo
            </button>
          </form>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-app-border bg-app-card/50">
        <div className="max-w-7xl mx-auto px-6 py-8 flex items-center justify-between">
          <p className="text-sm text-app-muted">
            &copy; 2026 AI Knowledge Graph Builder. Semester Project.
          </p>
          <div className="flex items-center gap-6">
            <Link href="/terms" className="text-sm text-app-muted hover:text-app-text transition-colors">
              Terms of Service
            </Link>
            <Link href="/contact" className="text-sm text-app-muted hover:text-app-text transition-colors">
              Contact
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
