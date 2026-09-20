import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'favicon-ico-alias',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.url === '/favicon.ico') {
            res.statusCode = 302;
            res.setHeader('Location', '/favicon.svg');
            res.end();
            return;
          }
          next();
        });
      },
    },
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@shared': path.resolve(__dirname, 'shared'),
      'three/addons': path.resolve(__dirname, 'node_modules/three/examples/jsm'),
    },
  },
  optimizeDeps: {
    // TalkingHead loads lipsync-*.mjs via dynamic import(); pre-bundling breaks those paths.
    exclude: ['@met4citizen/talkinghead'],
    include: [
      'three',
      'three/addons/controls/OrbitControls.js',
      'three/addons/renderers/CSS2DRenderer.js',
      'three/addons/loaders/GLTFLoader.js',
      'three/addons/loaders/DRACOLoader.js',
      'three/addons/loaders/FBXLoader.js',
      'three/addons/environments/RoomEnvironment.js',
      'three/addons/libs/stats.module.js',
    ],
    entries: ['index.html', 'src/**/*.{ts,tsx,js}'],
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    hmr: {
      host: '127.0.0.1',
      port: 5173,
      protocol: 'ws',
      clientPort: 5173,
    },
    fs: {
      allow: ['.'],
      deny: ['companions/**'],
    },
    proxy: {
      '/api': 'http://127.0.0.1:8787',
      '/ws': {
        target: 'ws://127.0.0.1:8787',
        ws: true,
        // Avoid noisy ECONNRESET when the mesh server restarts under tsx watch
        configure: (proxy) => {
          proxy.on('error', () => {
            /* mesh WS will reconnect from the client */
          });
        },
      },
      '/viz': 'http://127.0.0.1:8787',
      '/vault': 'http://127.0.0.1:8787',
      '/config': 'http://127.0.0.1:8787',
      '/identity': 'http://127.0.0.1:8787',
      '/companions': 'http://127.0.0.1:8787',
      '/visualizations': 'http://127.0.0.1:8787',
      '/higgsfield-clips': 'http://127.0.0.1:8787',
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          three: ['three'],
        },
      },
    },
    chunkSizeWarningLimit: 700,
  },
});
