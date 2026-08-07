import Link from "next/link";

export default function HomePage() {
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
            <Link href="/contact" className="text-sm text-slate hover:text-ink transition-colors">
              Contact
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

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 py-20 text-center">
        <h1 className="font-display text-5xl font-bold text-ink mb-6 leading-tight">
          Transform Documents Into
          <br />
          <span className="text-amber">Navigable Knowledge</span>
        </h1>
        <p className="text-lg text-slate max-w-2xl mx-auto mb-10">
          Upload your documents and watch them become an interconnected knowledge graph.
          Ask questions, discover relationships, and extract insights with AI-powered analysis.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link
            href="/auth/signup"
            className="px-8 py-3 bg-ink text-paper font-medium rounded-lg hover:bg-ink/90 transition-colors text-lg"
          >
            Get Started Free
          </Link>
          <form action="/auth/demo-login" method="post" className="inline">
            <button
              type="submit"
              className="px-8 py-3 border border-slate/30 text-ink font-medium rounded-lg hover:bg-slate/5 transition-colors text-lg"
            >
              Try the Demo
            </button>
          </form>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-7xl mx-auto px-6 py-16 border-t border-slate/20">
        <h2 className="font-display text-3xl font-semibold text-ink text-center mb-12">
          How It Works
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="bg-white rounded-lg border border-slate/20 p-6">
            <div className="w-10 h-10 bg-amber/20 rounded-lg flex items-center justify-center mb-4">
              <span className="text-amber font-bold text-lg">1</span>
            </div>
            <h3 className="font-display text-lg font-semibold text-ink mb-2">Upload Documents</h3>
            <p className="text-slate text-sm">
              Drop PDFs, Word docs, text files, or images. Our pipeline parses, chunks, and indexes
              everything automatically.
            </p>
          </div>
          <div className="bg-white rounded-lg border border-slate/20 p-6">
            <div className="w-10 h-10 bg-amber/20 rounded-lg flex items-center justify-center mb-4">
              <span className="text-amber font-bold text-lg">2</span>
            </div>
            <h3 className="font-display text-lg font-semibold text-ink mb-2">AI Extracts Knowledge</h3>
            <p className="text-slate text-sm">
              Entities, relationships, and key concepts are extracted using spaCy NER and LLM analysis,
              building a knowledge graph as you add documents.
            </p>
          </div>
          <div className="bg-white rounded-lg border border-slate/20 p-6">
            <div className="w-10 h-10 bg-amber/20 rounded-lg flex items-center justify-center mb-4">
              <span className="text-amber font-bold text-lg">3</span>
            </div>
            <h3 className="font-display text-lg font-semibold text-ink mb-2">Explore & Ask</h3>
            <p className="text-slate text-sm">
              Chat with your knowledge base, explore the graph visually, run AI agents for deeper analysis,
              and connect external tools via MCP.
            </p>
          </div>
        </div>
      </section>

      {/* Tech Stack */}
      <section className="max-w-7xl mx-auto px-6 py-16 border-t border-slate/20">
        <h2 className="font-display text-3xl font-semibold text-ink text-center mb-8">
          Built With
        </h2>
        <div className="flex flex-wrap justify-center gap-4">
          {["Next.js", "FastAPI", "PostgreSQL", "ChromaDB", "NetworkX", "LangGraph", "spaCy", "OpenAI", "React Flow"].map(
            (tech) => (
              <span
                key={tech}
                className="px-4 py-2 bg-white border border-slate/20 rounded-lg text-sm text-ink font-medium"
              >
                {tech}
              </span>
            )
          )}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-7xl mx-auto px-6 py-20 text-center border-t border-slate/20">
        <h2 className="font-display text-3xl font-semibold text-ink mb-4">
          Ready to Build Your Knowledge Graph?
        </h2>
        <p className="text-slate mb-8 max-w-xl mx-auto">
          Start with a free account. Upload your first document in seconds.
        </p>
        <Link
          href="/auth/signup"
          className="px-8 py-3 bg-ink text-paper font-medium rounded-lg hover:bg-ink/90 transition-colors text-lg"
        >
          Create Free Account
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate/20 bg-white/50">
        <div className="max-w-7xl mx-auto px-6 py-8 flex items-center justify-between">
          <p className="text-sm text-slate">
            &copy; 2026 AI Knowledge Graph Builder. Semester Project.
          </p>
          <div className="flex items-center gap-6">
            <Link href="/terms" className="text-sm text-slate hover:text-ink transition-colors">
              Terms of Service
            </Link>
            <Link href="/contact" className="text-sm text-slate hover:text-ink transition-colors">
              Contact
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
