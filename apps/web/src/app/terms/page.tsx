import Link from "next/link";

export default function TermsPage() {
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
        <h1 className="font-display text-4xl font-bold text-ink mb-6">Terms of Service</h1>
        <p className="text-slate text-sm mb-8">Last updated: August 2026</p>

        <div className="prose prose-slate max-w-none space-y-8">
          <section>
            <h2 className="font-display text-2xl font-semibold text-ink mb-3">1. Acceptance of Terms</h2>
            <p className="text-slate">
              By accessing or using the AI Knowledge Graph Builder (&quot;the Service&quot;), you agree to be
              bound by these Terms of Service. If you do not agree, do not use the Service.
            </p>
          </section>

          <section>
            <h2 className="font-display text-2xl font-semibold text-ink mb-3">2. Description of Service</h2>
            <p className="text-slate">
              The Service allows users to upload documents, which are processed to extract entities and
              relationships, forming a knowledge graph. Users can then search, chat with, and explore
              the knowledge graph using AI-powered tools.
            </p>
          </section>

          <section>
            <h2 className="font-display text-2xl font-semibold text-ink mb-3">3. User Accounts</h2>
            <p className="text-slate">
              You are responsible for maintaining the confidentiality of your account credentials.
              You agree to notify us immediately of any unauthorized use of your account.
            </p>
          </section>

          <section>
            <h2 className="font-display text-2xl font-semibold text-ink mb-3">4. User Content</h2>
            <p className="text-slate">
              You retain ownership of documents you upload. By uploading content, you grant us
              permission to process, index, and analyze the content solely to provide the Service.
              We do not share your documents with third parties.
            </p>
          </section>

          <section>
            <h2 className="font-display text-2xl font-semibold text-ink mb-3">5. Acceptable Use</h2>
            <p className="text-slate">
              You agree not to: upload malicious content, attempt to breach security measures,
              use the Service for illegal purposes, or attempt to reverse-engineer the AI models.
            </p>
          </section>

          <section>
            <h2 className="font-display text-2xl font-semibold text-ink mb-3">6. Limitation of Liability</h2>
            <p className="text-slate">
              The Service is provided &quot;as is&quot; for educational and demonstration purposes. We make
              no warranties about accuracy, availability, or fitness for a particular purpose.
            </p>
          </section>

          <section>
            <h2 className="font-display text-2xl font-semibold text-ink mb-3">7. Changes to Terms</h2>
            <p className="text-slate">
              We may update these terms at any time. Continued use of the Service after changes
              constitutes acceptance of the new terms.
            </p>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate/20 bg-white/50 mt-16">
        <div className="max-w-7xl mx-auto px-6 py-8 flex items-center justify-between">
          <p className="text-sm text-slate">
            &copy; 2026 AI Knowledge Graph Builder. Semester Project.
          </p>
          <div className="flex items-center gap-6">
            <Link href="/contact" className="text-sm text-slate hover:text-ink transition-colors">
              Contact
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
