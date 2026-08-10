import type { NextConfig } from "next";

// Fail the build if someone tries to ship mock auth in a production build.
if (process.env.NODE_ENV === "production" && process.env.NEXT_PUBLIC_MOCK_AUTH === "true") {
  throw new Error(
    "NEXT_PUBLIC_MOCK_AUTH=true is not allowed in a production build. " +
      "Configure real Supabase credentials instead."
  );
}

const nextConfig: NextConfig = {
  transpilePackages: ["shared-types"],
};

export default nextConfig;
