import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#070a12",
          900: "#0b0f1a",
          800: "#121829",
          700: "#1b2235",
          600: "#283047",
        },
        accent: {
          DEFAULT: "#7c6cff",
          glow: "#9d8cff",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
      },
      animation: { float: "float 6s ease-in-out infinite" },
    },
  },
  plugins: [],
};

export default config;
