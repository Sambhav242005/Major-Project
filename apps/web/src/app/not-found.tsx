import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-app-bg text-app-text">
      <h1 className="text-xl font-semibold mb-4">Page not found</h1>
      <p className="text-app-muted mb-6">
        The page you are looking for does not exist.
      </p>
      <Link
        href="/"
        className="px-6 py-2 bg-amber dark:text-app-bg rounded-lg hover:bg-amber/90 transition-colors text-sm"
      >
        Go home
      </Link>
    </div>
  );
}
