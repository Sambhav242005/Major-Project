import Link from "next/link";
import { PublicHeader } from "@/components/public-header";
import { Reveal } from "@/components/motion/reveal";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-app-bg">
      <PublicHeader />

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 py-20 text-center">
        <Reveal>
          <h1 className="font-display text-5xl font-bold text-app-text mb-6 leading-tight">
            Transform Documents Into
            <br />
            <span className="text-amber">Navigable Knowledge</span>
          </h1>
          <p className="text-lg text-app-muted max-w-2xl mx-auto mb-10">
            Upload your documents and watch them become an interconnected knowledge graph.
            Ask questions, discover relationships, and extract insights with AI-powered analysis.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link
              href="/auth/signup"
              className="px-8 py-3 bg-brand-accent/15 text-app-text font-medium rounded-lg hover:bg-brand-accent/25 transition-colors text-lg"
            >
              Get Started Free
            </Link>
            <form action="/auth/demo-login" method="post" className="inline">
              <button
                type="submit"
                className="px-8 py-3 border border-app-border-strong text-app-text font-medium rounded-lg hover:bg-app-card-hover transition-colors text-lg"
              >
                Try the Demo
              </button>
            </form>
          </div>
        </Reveal>
      </section>

      {/* Features */}
      <section className="max-w-7xl mx-auto px-6 py-16 border-t border-app-border">
        <h2 className="font-display text-3xl font-semibold text-app-text text-center mb-12">
          How It Works
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <Reveal delay={0}>
            <div className="bg-app-card rounded-lg border border-app-border p-6 h-full">
              <div className="w-10 h-10 bg-amber/20 rounded-lg flex items-center justify-center mb-4">
                <span className="text-amber font-bold text-lg">1</span>
              </div>
              <h3 className="font-display text-lg font-semibold text-app-text mb-2">Upload Documents</h3>
              <p className="text-app-muted text-sm">
                Drop PDFs, Word docs, text files, or images. Our pipeline parses, chunks, and indexes
                everything automatically.
              </p>
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <div className="bg-app-card rounded-lg border border-app-border p-6 h-full">
              <div className="w-10 h-10 bg-amber/20 rounded-lg flex items-center justify-center mb-4">
                <span className="text-amber font-bold text-lg">2</span>
              </div>
              <h3 className="font-display text-lg font-semibold text-app-text mb-2">AI Extracts Knowledge</h3>
              <p className="text-app-muted text-sm">
                Entities, relationships, and key concepts are extracted using spaCy NER and LLM analysis,
                building a knowledge graph as you add documents.
              </p>
            </div>
          </Reveal>
          <Reveal delay={0.2}>
            <div className="bg-app-card rounded-lg border border-app-border p-6 h-full">
              <div className="w-10 h-10 bg-amber/20 rounded-lg flex items-center justify-center mb-4">
                <span className="text-amber font-bold text-lg">3</span>
              </div>
              <h3 className="font-display text-lg font-semibold text-app-text mb-2">Explore & Ask</h3>
              <p className="text-app-muted text-sm">
                Chat with your knowledge base, explore the graph visually, run AI agents for deeper analysis,
                and connect external tools via MCP.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Tech Stack */}
      <section className="max-w-7xl mx-auto px-6 py-16 border-t border-app-border">
        <h2 className="font-display text-3xl font-semibold text-app-text text-center mb-8">
          Built With
        </h2>
        <div className="flex flex-wrap justify-center gap-4">
          {["Next.js", "FastAPI", "PostgreSQL", "ChromaDB", "NetworkX", "LangGraph", "spaCy", "OpenAI", "React Flow"].map(
            (tech) => (
              <span
                key={tech}
                className="px-4 py-2 bg-app-card border border-app-border rounded-lg text-sm text-app-muted font-medium"
              >
                {tech}
              </span>
            )
          )}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-7xl mx-auto px-6 py-20 text-center border-t border-app-border">
        <Reveal>
          <h2 className="font-display text-3xl font-semibold text-app-text mb-4">
            Ready to Build Your Knowledge Graph?
          </h2>
          <p className="text-app-muted mb-8 max-w-xl mx-auto">
            Start with a free account. Upload your first document in seconds.
          </p>
          <Link
            href="/auth/signup"
            className="px-8 py-3 bg-brand-accent/15 text-app-text font-medium rounded-lg hover:bg-brand-accent/25 transition-colors text-lg"
          >
            Create Free Account
          </Link>
        </Reveal>
      </section>

      {/* Footer */}
      <footer className="border-t border-app-border bg-app-card/50">
        <div className="max-w-7xl mx-auto px-6 py-8 flex items-center justify-between">
          <p className="text-sm text-app-muted">
            &copy; 2026 AI Knowledge Graph Builder.
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
