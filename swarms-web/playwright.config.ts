import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'url';
import path from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
  testDir: path.join(__dirname, 'tests/e2e'),
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5002',
    headless: true,
  },
  webServer: {
    command: 'python run.py',
    url: 'http://localhost:5002',
    reuseExistingServer: !process.env.CI,
    cwd: __dirname,
    timeout: 120000,
  },
});
