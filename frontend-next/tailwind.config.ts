import type { Config } from "tailwindcss";

// Paleta "wealth management premium" pedida pelo usuário: navy/black
// profundo de fundo, cards azul-marinho escuro, primário roxo/neon,
// secundário azul, semânticas positivo/atenção/crítico.
const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#05070D",
        surface: "#0B1020",
        "surface-hover": "#111834",
        border: "#1E2740",
        "border-soft": "#161D33",
        primary: {
          DEFAULT: "#8B5CF6",
          foreground: "#FFFFFF",
          glow: "#A78BFA",
        },
        secondary: {
          DEFAULT: "#3B82F6",
          foreground: "#FFFFFF",
        },
        positive: "#22C55E",
        attention: "#F59E0B",
        critical: "#EF4444",
        info: "#38BDF8",
        "text-primary": "#F5F7FB",
        "text-muted": "#8B93A8",
        "text-faint": "#5B6478",
      },
      backgroundImage: {
        "gradient-primary": "linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)",
        "gradient-glow": "radial-gradient(circle at top left, rgba(139,92,246,0.18), transparent 60%)",
        "gradient-positive": "linear-gradient(135deg, #22C55E 0%, #16A34A 100%)",
      },
      borderRadius: {
        card: "16px",
      },
      boxShadow: {
        card: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 8px 24px -12px rgba(0,0,0,0.5)",
        glow: "0 0 0 1px rgba(139,92,246,0.25), 0 0 24px -4px rgba(139,92,246,0.35)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
