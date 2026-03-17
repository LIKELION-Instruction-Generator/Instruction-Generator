import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--color-canvas)",
        surface: "var(--color-surface)",
        shell: "var(--color-shell)",
        ink: "var(--color-ink)",
        muted: "var(--color-muted)",
        border: "var(--color-border)",
        accent: {
          DEFAULT: "var(--color-accent)",
          strong: "var(--color-accent-strong)",
          soft: "var(--color-accent-soft)",
        },
        success: "var(--color-success)",
        danger: "var(--color-danger)",
        warning: "var(--color-warning)",
      },
      fontFamily: {
        display: ["Lexend", "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["Lexend", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        panel: "0 20px 45px rgba(127, 74, 24, 0.08)",
        glow: "0 18px 45px rgba(255, 107, 0, 0.18)",
      },
      backgroundImage: {
        "hero-flow":
          "radial-gradient(circle at 0% 0%, rgba(255, 132, 53, 0.85), transparent 42%), radial-gradient(circle at 80% 20%, rgba(255, 209, 168, 0.95), transparent 36%), linear-gradient(135deg, #38190b 0%, #9c3600 55%, #ff7b2c 100%)",
        "canvas-glow":
          "radial-gradient(circle at top right, rgba(255, 184, 118, 0.25), transparent 30%), radial-gradient(circle at bottom left, rgba(247, 132, 64, 0.18), transparent 35%)",
      },
    },
  },
  plugins: [],
} satisfies Config;
