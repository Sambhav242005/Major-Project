import type { Metadata } from "next";
import "./globals.css";
import { LazyMotion, domAnimation } from "motion/react";
import { cn } from "@/lib/utils";
import { ThemeProvider } from "@/components/theme-provider";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const metadata: Metadata = {
  title: "AI Knowledge Graph Builder",
  description: "Transform documents into a navigable knowledge graph",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={cn("font-sans")}>
      <body>
        <LazyMotion features={domAnimation} strict>
          <ThemeProvider>
            <ErrorBoundary>{children}</ErrorBoundary>
          </ThemeProvider>
        </LazyMotion>
      </body>
    </html>
  );
}
