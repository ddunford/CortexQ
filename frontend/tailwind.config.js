/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // CortexQ Brand Colors
        cortex: {
          primary: '#2A5DFF',     // Primary Blue
          navy: '#0A1A3D',        // Deep Navy
          aqua: '#00D1FF',        // Aqua Accent
          grey: '#F4F5F7',        // Soft Grey
          slate: '#5B6770',       // Slate Grey
          lime: '#B2FF59',        // Lime Pop
        },
        // Maintain compatibility with existing colors
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#2A5DFF',         // CortexQ Primary
          600: '#2A5DFF',         // CortexQ Primary
          700: '#0A1A3D',         // CortexQ Navy
        },
      },
    },
  },
  plugins: [],
}; 