import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Capgemini Brand Colors
        primary: {
          DEFAULT: "#0070AD",
          light: "#12ABDB",
          dark: "#1B365D",
          50: "#E6F3FA",
          100: "#CCE7F5",
          200: "#99CFEB",
          300: "#66B7E1",
          400: "#3399D6",
          500: "#0070AD",
          600: "#005A8A",
          700: "#004368",
          800: "#002D45",
          900: "#1B365D",
        },
        navy: {
          DEFAULT: "#1B365D",
          50: "#E8ECF1",
          100: "#D1D9E3",
          200: "#A3B3C7",
          300: "#7590AB",
          400: "#476D8F",
          500: "#1B365D",
          600: "#162C4D",
          700: "#11213A",
          800: "#0D1928",
          900: "#0A1220",
          950: "#070D17",
        },
        accent: {
          DEFAULT: "#12ABDB",
          light: "#4CC3E8",
          dark: "#0E89AF",
        },
        deepPurple: {
          DEFAULT: "#2B0A3D",
          light: "#3D1456",
          dark: "#1A0625",
        },
        surface: {
          DEFAULT: "#ffffff",
          dark: "#0D1928",
        },
        panel: {
          DEFAULT: "#F5F5F5",
          dark: "#11213A",
        },
        capText: {
          DEFAULT: "#333333",
          light: "#666666",
          muted: "#999999",
        },
      },
      fontFamily: {
        sans: [
          "Ubuntu",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Fira Code", "ui-monospace", "monospace"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "capgemini-gradient": "linear-gradient(135deg, #1B365D 0%, #0070AD 100%)",
      },
      boxShadow: {
        subtle: "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)",
        card: "0 2px 8px rgba(0,0,0,0.08)",
        "card-hover": "0 4px 16px rgba(0,0,0,0.12)",
        glass: "0 8px 32px rgba(0,0,0,0.12)",
        "glass-lg": "0 16px 48px rgba(0,0,0,0.2)",
      },
      animation: {
        "fade-in": "fadeIn 0.2s ease-out",
        "slide-in": "slideIn 0.3s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideIn: {
          "0%": { transform: "translateX(20px)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        slideUp: {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
} satisfies Config;
