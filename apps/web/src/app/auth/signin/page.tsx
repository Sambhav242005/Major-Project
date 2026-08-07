"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

const MOCK_AUTH = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";

export default function SignIn() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const supabase = createClient();

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    router.push("/dashboard");
    router.refresh();
  };

  const handleMockLogin = async () => {
    setLoading(true);
    // Set mock session cookie
    document.cookie = "mock-session=mock-user-001; path=/; max-age=3600";
    router.push("/dashboard");
    router.refresh();
  };

  const handleGoogleSignIn = async () => {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper">
      <div className="w-full max-w-md px-6">
        <h1 className="font-display text-3xl font-semibold text-ink mb-2 text-center">
          Welcome back
        </h1>
        <p className="text-slate text-center mb-8">
          Sign in to access your knowledge base
        </p>

        {MOCK_AUTH && (
          <form action="/auth/demo-login" method="post">
            <button
              type="submit"
              className="w-full py-3 bg-amber text-ink font-medium rounded-lg hover:bg-amber/90 mb-4 border-2 border-amber/50"
            >
              Try Demo (Auto-Login)
            </button>
          </form>
        )}

        <div className="my-6 flex items-center gap-3">
          <div className="flex-1 h-px bg-slate/20" />
          <span className="text-xs text-slate">or sign in with email</span>
          <div className="flex-1 h-px bg-slate/20" />
        </div>

        <form onSubmit={handleSignIn} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-ink mb-1">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2 border border-slate/30 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber bg-white text-ink"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-ink mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-3 py-2 border border-slate/30 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber bg-white text-ink"
            />
          </div>

          {error && (
            <p className="text-rust text-sm">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-ink text-paper font-medium rounded-lg hover:bg-ink/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <div className="my-6 flex items-center gap-3">
          <div className="flex-1 h-px bg-slate/20" />
          <span className="text-xs text-slate">or</span>
          <div className="flex-1 h-px bg-slate/20" />
        </div>

        <button
          onClick={handleGoogleSignIn}
          className="w-full py-2.5 border border-slate/30 text-ink font-medium rounded-lg hover:bg-slate/5"
        >
          Continue with Google
        </button>

        <p className="mt-6 text-center text-sm text-slate">
          Don&apos;t have an account?{" "}
          <Link href="/auth/signup" className="text-amber hover:underline font-medium">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}
