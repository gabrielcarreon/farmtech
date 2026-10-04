/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f4f0e6",
        ink: "#1a2820",
        canopy: "#1e4632",
        leaf: "#3e6b4a",
        mist: "#d5e2d4",
        clay: "#9a3f24",
        gold: "#a86b12",
        line: "#c9b89a",
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        body: ["Figtree", "sans-serif"],
      },
      boxShadow: {
        ledger: "0 18px 50px rgba(26, 40, 32, 0.08)",
      },
    },
  },
  plugins: [],
};
