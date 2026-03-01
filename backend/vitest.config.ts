import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  resolve: {
    // Allow Vitest/Vite to resolve .js imports to .ts source files
    // (needed because source code uses NodeNext module resolution with .js extensions)
    extensions: ['.ts', '.js', '.mjs', '.json'],
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.ts'],
      exclude: ['src/jobs/worker.ts', 'src/server.ts'],
    },
    setupFiles: ['tests/setup.ts'],
    testTimeout: 15000,
  },
});
