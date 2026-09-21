import Link from "next/link";
import { ThemeToggle } from "@/components/theme-toggle";

export function PublicHeader() {
  return (
    <header className="border-b border-app-border bg-app-header-bg backdrop-blur-sm sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link href="/" className="font-display text-xl font-semibold text-app-text">
          AI Knowledge Graph Builder
        </Link>
        <div className="flex items-center gap-4">
          <Link href="/demo" className="text-sm text-app-muted hover:text-app-text transition-colors">
            Demo
          </Link>
          <Link href="/contact" className="text-sm text-app-muted hover:text-app-text transition-colors">
            Contact
          </Link>
          <Link href="/auth/signin" className="text-sm text-app-muted hover:text-app-text transition-colors">
            Sign in
          </Link>
          <Link
            href="/auth/signup"
            className="px-4 py-2 bg-app-text text-app-bg text-sm font-medium rounded-lg hover:opacity-90 transition-opacity"
          >
            Sign up
          </Link>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
