import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'url';
import path from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5002';
const projectRoot = path.resolve(__dirname, '..');

export default defineConfig({
  testDir: path.join(__dirname, 'tests/e2e'),
  use: {
    baseURL,
    headless: true,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `${process.env.PLAYWRIGHT_PYTHON ?? 'python'} run.py`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    cwd: projectRoot,
    timeout: 120000,
    env: {
      PORT: new URL(baseURL).port || '5002',
      PYTHONUNBUFFERED: '1',
    },
  },
});
