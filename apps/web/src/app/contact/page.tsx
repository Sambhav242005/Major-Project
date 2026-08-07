import Link from "next/link";

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-paper">
      {/* Header */}
      <header className="border-b border-slate/20 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="font-display text-xl font-semibold text-ink">
            AI Knowledge Graph Builder
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/demo" className="text-sm text-slate hover:text-ink transition-colors">
              Demo
            </Link>
            <Link href="/auth/signin" className="text-sm text-slate hover:text-ink transition-colors">
              Sign in
            </Link>
            <Link
              href="/auth/signup"
              className="px-4 py-2 bg-ink text-paper text-sm font-medium rounded-lg hover:bg-ink/90 transition-colors"
            >
              Sign up
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="font-display text-4xl font-bold text-ink mb-6">Contact Us</h1>
        <p className="text-slate text-lg mb-10">
          Have questions, feedback, or want to collaborate? We&apos;d love to hear from you.
        </p>

        <div className="bg-white rounded-lg border border-slate/20 p-8 mb-8">
          <h2 className="font-display text-xl font-semibold text-ink mb-4">Get in Touch</h2>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-ink block mb-1">Name</label>
              <input
                type="text"
                placeholder="Your name"
                className="w-full px-4 py-2 border border-slate/30 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber bg-white text-ink"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-ink block mb-1">Email</label>
              <input
                type="email"
                placeholder="your@email.com"
                className="w-full px-4 py-2 border border-slate/30 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber bg-white text-ink"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-ink block mb-1">Message</label>
              <textarea
                rows={5}
                placeholder="How can we help?"
                className="w-full px-4 py-2 border border-slate/30 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber bg-white text-ink resize-none"
              />
            </div>
            <button
              type="button"
              className="px-6 py-2 bg-ink text-paper font-medium rounded-lg hover:bg-ink/90 transition-colors"
            >
              Send Message
            </button>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-slate/20 p-8">
          <h2 className="font-display text-xl font-semibold text-ink mb-4">Project Details</h2>
          <p className="text-slate text-sm mb-4">
            This is a college semester project demonstrating AI-powered knowledge graph construction
            from documents. The system uses modern NLP, vector search, and graph databases to
            transform unstructured text into navigable knowledge.
          </p>
          <p className="text-slate text-sm">
            Tech stack: Next.js, FastAPI, PostgreSQL, ChromaDB, NetworkX, LangGraph, spaCy, OpenAI.
          </p>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate/20 bg-white/50 mt-16">
        <div className="max-w-7xl mx-auto px-6 py-8 flex items-center justify-between">
          <p className="text-sm text-slate">
            &copy; 2026 AI Knowledge Graph Builder. Semester Project.
          </p>
          <div className="flex items-center gap-6">
            <Link href="/terms" className="text-sm text-slate hover:text-ink transition-colors">
              Terms of Service
            </Link>
            <Link href="/" className="text-sm text-slate hover:text-ink transition-colors">
              Home
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
