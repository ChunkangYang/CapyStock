import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    exclude: ['**/e2e/**', '**/node_modules/**'],
  },
  resolve: {
    alias: {
      $lib: new URL('src/lib', import.meta.url).pathname,
      $app: new URL('src', import.meta.url).pathname,
    },
  },
});
