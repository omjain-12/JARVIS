/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Segoe UI Variable"', '"Segoe UI"', '"Segoe UI Emoji"', '"Segoe UI Symbol"', '-apple-system', 'BlinkMacSystemFont', 'Roboto', 'sans-serif'],
      },
      colors: {
        jarvis: {
          bg: "var(--jarvis-bg)",
          surface: "var(--jarvis-surface)",
          panel: "var(--jarvis-panel)",
          sidebar: "var(--jarvis-sidebar)",
          border: "var(--jarvis-border)",
          accent: "var(--jarvis-accent)",
          "accent-primary": "var(--jarvis-accent-primary)",
          "accent-secondary": "var(--jarvis-accent-secondary)",
          "accent-hover": "var(--jarvis-accent-hover)",
          text: "var(--jarvis-text)",
          "text-secondary": "var(--jarvis-text-secondary)",
          muted: "var(--jarvis-muted)",
          user: "var(--jarvis-user)",
          assistant: "var(--jarvis-assistant)",

          success: "#32D583",
          warning: "#FDB022",
          danger: "#F04438",
        },
      },
      backgroundImage: {
        'copilot-gradient': 'linear-gradient(135deg, #10A5F5 0%, #0060DF 30%, #9048E1 70%, #D4429E 100%)',
      },
      boxShadow: {
        "panel": "var(--jarvis-shadow-panel)",
        "card-hover": "var(--jarvis-shadow-card)",
        "focus-ring": "var(--jarvis-shadow-focus)",
      },
      animation: {
        "pulse-dot": "pulseDot 1.4s ease-in-out infinite",
        "float": "float 6s ease-in-out infinite",
        "float-slow": "float 8s ease-in-out infinite",
        "float-fast": "float 4s ease-in-out infinite",
        "glow-pulse": "glowPulse 3s infinite",
      },
      keyframes: {
        pulseDot: {
          "0%, 80%, 100%": { opacity: "0.2", transform: "scale(0.8)" },
          "40%": { opacity: "1", transform: "scale(1.1)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" },
        },
        glowPulse: {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.8", transform: "scale(1.02)" },
        }
      },
    },
  },
  plugins: [],
};
