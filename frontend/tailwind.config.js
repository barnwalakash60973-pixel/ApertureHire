/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          DEFAULT: "var(--color-base)",
          surface: "var(--color-surface)",
          surface2: "var(--color-surface-2)",
          border: "var(--color-border)",
        },
        ink: {
          DEFAULT: "var(--color-ink)",
          muted: "var(--color-ink-muted)",
          faint: "var(--color-ink-faint)",
        },
        signal: {
          DEFAULT: "var(--color-signal)",
          soft: "var(--color-signal-soft)",
        },
        grade: {
          strong_hire: "#1FB37A",
          hire: "#5FBF6E",
          lean_hire: "#D9A62E",
          no_hire: "#E27A3F",
          strong_no_hire: "#E24E4E",
        },
      },
      fontFamily: {
        sans: [
          "Inter var",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "IBM Plex Mono",
          "SF Mono",
          "JetBrains Mono",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      borderRadius: {
        xl2: "1.25rem",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(0,0,0,0.06), 0 8px 24px -8px rgba(0,0,0,0.18)",
        glow: "0 0 0 1px var(--color-border), 0 10px 40px -12px var(--color-signal-soft)",
      },
      keyframes: {
        pulseSlow: {
          "0%, 100%": { opacity: 1 },
          "50%": { opacity: 0.55 },
        },
      },
      animation: {
        pulseSlow: "pulseSlow 2.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
