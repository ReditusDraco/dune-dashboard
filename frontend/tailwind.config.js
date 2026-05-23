/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: ["class", '[data-theme="emperor"]'],
  theme: {
    extend: {
      colors: {
        primary: "var(--primary)",
        "primary-dark": "var(--primary-dark)",
        "primary-light": "var(--primary-light)",
        background: "var(--bg)",
        "card-bg": "var(--card-bg)",
        "text-primary": "var(--text)",
        "text-secondary": "var(--text-light)",
        "text-muted": "var(--text-muted)",
        border: "var(--border)",
        accent: "var(--accent)",
        danger: "var(--danger)",
        success: "var(--success)",
        "nav-bg": "var(--nav-bg)",
        "nav-text": "var(--nav-text)",
        "nav-active": "var(--nav-active)",
        hover: "var(--hover)",
      },
      fontFamily: {
        serif: ["Playfair Display", "serif"],
        sans: ["Inter", "sans-serif"],
        mono: ["Roboto Mono", "monospace"],
      },
      boxShadow: {
        card: "var(--shadow)",
      },
    },
  },
  plugins: [],
}
