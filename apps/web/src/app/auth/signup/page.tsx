"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

export default function SignUp() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const supabaseRef = useRef(createClient());

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const { error } = await supabaseRef.current.auth.signUp({
      email,
      password,
      options: {
        data: { full_name: fullName },
      },
    });

    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    router.push("/dashboard");
    router.refresh();
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-app-bg">
      <div className="w-full max-w-md px-6">
        <h1 className="font-display text-3xl font-semibold text-app-text mb-2 text-center">
          Create your account
        </h1>
        <p className="text-app-muted text-center mb-8">
          Start building your knowledge base
        </p>

        <form onSubmit={handleSignUp} className="space-y-4">
          <div>
            <label htmlFor="fullName" className="block text-sm font-medium text-app-text mb-1">
              Full name
            </label>
            <input
              id="fullName"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              className="w-full px-3 py-2 border border-app-border-strong rounded-lg focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber bg-app-card text-app-text"
            />
          </div>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-app-text mb-1">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2 border border-app-border-strong rounded-lg focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber bg-app-card text-app-text"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-app-text mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full px-3 py-2 border border-app-border-strong rounded-lg focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber bg-app-card text-app-text"
            />
          </div>

          {error && (
            <p className="text-rust text-sm">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-app-text text-app-bg font-medium rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Creating account..." : "Sign up"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-app-muted">
          Already have an account?{" "}
          <Link href="/auth/signin" className="text-amber-400 hover:underline font-medium">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
