/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sanbao: {
          navy: '#0C1D36',      // Fondo barra lateral institucional
          dark: '#0F2447',      // Azul oscuro de contraste
          primary: '#1A56B2',   // Azul San Bao oficial del isotipo
          light: '#2563EB',     // Azul interactivo
          hover: '#174794',     // Hover de botones primarios
          soft: '#EBF2FC',      // Fondo suave para badges de estado
          accent: '#3B82F6',    // Acentos celestes
          bg: '#F8FAFC',        // Fondo general limpio
          card: '#FFFFFF',
          border: '#E2E8F0',
        },
      },
      fontFamily: {
        serif: ['"Cinzel"', '"Trajan Pro"', '"Cinzel Decorative"', 'Georgia', 'serif'],
      },
    },
  },
  plugins: [],
}
