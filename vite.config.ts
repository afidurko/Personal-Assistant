import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@shared': path.resolve(__dirname, 'shared'),
    },
  },
  // 3D cortex lives under visualizations/ and loads three via importmap from Express.
  // Keep Vite out of that tree so it does not try to resolve CDN modules.
  optimizeDeps: {
    entries: ['index.html', 'src/**/*.{ts,tsx}'],
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    fs: {
      allow: ['.'],
      deny: ['visualizations/**', 'companions/**'],
    },
    proxy: {
      '/api': 'http://127.0.0.1:8787',
      '/ws': {
        target: 'ws://127.0.0.1:8787',
        ws: true,
      },
      '/viz': 'http://127.0.0.1:8787',
      '/vault': 'http://localhost:8787',
      '/config': 'http://127.0.0.1:8787',
      '/identity': 'http://127.0.0.1:8787',
      '/companions': 'http://127.0.0.1:8787',
      '/visualizations': 'http://127.0.0.1:8787',
    },
  },
});
