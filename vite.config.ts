import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@shared': path.resolve(__dirname, 'shared'),
      'three/addons': path.resolve(__dirname, 'node_modules/three/examples/jsm'),
    },
  },
  optimizeDeps: {
    include: ['three', 'three/addons/controls/OrbitControls.js', 'three/addons/renderers/CSS2DRenderer.js'],
    entries: ['index.html', 'src/**/*.{ts,tsx,js}'],
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    fs: {
      allow: ['.'],
      deny: ['companions/**'],
    },
    proxy: {
      '/api': 'http://127.0.0.1:8787',
      '/ws': {
        target: 'ws://127.0.0.1:8787',
        ws: true,
      },
      '/viz': 'http://127.0.0.1:8787',
      '/vault': 'http://127.0.0.1:8787',
      '/config': 'http://127.0.0.1:8787',
      '/identity': 'http://127.0.0.1:8787',
      '/companions': 'http://127.0.0.1:8787',
      '/visualizations': 'http://127.0.0.1:8787',
    },
  },
});
