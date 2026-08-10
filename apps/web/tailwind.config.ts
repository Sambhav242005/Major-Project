import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Theme-aware app colors (switch with .dark/.light on <html>)
        "app-bg": "var(--app-bg)",
        "app-card": "var(--app-card)",
        "app-card-hover": "var(--app-card-hover)",
        "app-text": "var(--app-text)",
        "app-muted": "var(--app-muted)",
        "app-border": "var(--app-border)",
        "app-border-strong": "var(--app-border-strong)",
        "app-input-bg": "var(--app-input-bg)",
        "app-input-border": "var(--app-input-border)",
        "app-header-bg": "var(--app-header-bg)",
        "app-sidebar-bg": "var(--app-sidebar-bg)",
        "app-surface": "var(--app-surface)",
        "app-surface-alt": "var(--app-surface-alt)",
        // Brand (static, always same)
        amber: "#C9862B",
        rust: "#B4432F",
        // Brand accent — the one interactive highlight (replaces ad-hoc sky-500)
        "brand-accent": "#38bdf8",
        // Shadcn
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      fontFamily: {
        display: ["Fraunces", "serif"],
        sans: ["Inter", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [tailwindcssAnimate],
};

export default config;
