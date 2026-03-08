/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        jarvis: {
          bg: "#0f1117",
          surface: "#1a1d27",
          border: "#2a2d3a",
          accent: "#6366f1",
          "accent-hover": "#818cf8",
          text: "#e2e8f0",
          muted: "#94a3b8",
          user: "#3b82f6",
          assistant: "#1e293b",
        },
      },
      animation: {
        "pulse-dot": "pulseDot 1.4s ease-in-out infinite",
      },
      keyframes: {
        pulseDot: {
          "0%, 80%, 100%": { opacity: "0" },
          "40%": { opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};
