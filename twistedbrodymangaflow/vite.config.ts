import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['lucide-react', 'sharp'],
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:7860',
        changeOrigin: true,
      },
      '/hf-proxy': {
        target: 'https://codebydante-brodyfilestreambot.hf.space',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/hf-proxy/, '')
      }
    },
  },
});
