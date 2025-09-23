import { APIRequestContext, expect, test as base } from '@playwright/test';

import { MockedLettaController } from './mockedLetta.js';
import { MockAgent } from './mockData.js';

type SessionSummary = {
  id: string;
  created_at: string;
  last_updated: string;
  title: string | null;
  tags: string[];
};

type CreateSessionPayload = {
  title?: string | null;
  tags?: string[];
};

type SessionExport = {
  filename: string;
  size_bytes: number;
  created_at: string;
  kind: 'json' | 'markdown';
};

type CreateExportResponse = {
  ok: boolean;
  created?: { filename: string; kind: 'json' | 'markdown' }[];
  error?: string;
};

type CreateSessionFn = (overrides?: CreateSessionPayload) => Promise<SessionSummary>;
type ListSessionsFn = (options?: { limit?: number }) => Promise<SessionSummary[]>;
type CreateSessionExportFn = (sessionId: string) => Promise<CreateExportResponse>;
type ListSessionExportsFn = (sessionId: string, options?: { limit?: number }) => Promise<SessionExport[]>;

const defaultSessionPayload = (): Required<CreateSessionPayload> => ({
  title: 'Playwright Session',
  tags: ['playwright'],
});

async function createSessionViaApi(
  request: APIRequestContext,
  overrides: CreateSessionPayload | undefined
): Promise<SessionSummary> {
  const payload = { ...defaultSessionPayload(), ...overrides };
  const response = await request.post('/api/sessions', { data: payload });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as SessionSummary;
}

async function listSessionsViaApi(
  request: APIRequestContext,
  options?: { limit?: number }
): Promise<SessionSummary[]> {
  const params = new URLSearchParams();
  if (options?.limit !== undefined) {
    params.set('limit', String(options.limit));
  }
  const query = params.toString();
  const response = await request.get(`/api/sessions${query ? `?${query}` : ''}`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as SessionSummary[];
}

async function createSessionExportViaApi(
  request: APIRequestContext,
  sessionId: string
): Promise<CreateExportResponse> {
  const response = await request.post(`/api/sessions/${sessionId}/export`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as CreateExportResponse;
}

async function listSessionExportsViaApi(
  request: APIRequestContext,
  sessionId: string,
  options?: { limit?: number }
): Promise<SessionExport[]> {
  const params = new URLSearchParams();
  if (options?.limit !== undefined) {
    params.set('limit', String(options.limit));
  }
  const query = params.toString();
  const response = await request.get(
    `/api/sessions/${sessionId}/exports${query ? `?${query}` : ''}`
  );
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as SessionExport[];
}

export const test = base.extend<{
  mockedLetta: MockedLettaController;
  startConversation: (topic?: string) => Promise<void>;
  createSession: CreateSessionFn;
  listSessions: ListSessionsFn;
  createSessionExport: CreateSessionExportFn;
  listSessionExports: ListSessionExportsFn;
  setAgents: (agents: MockAgent[]) => Promise<void>;
}>(
  {
    mockedLetta: async ({ page }, use) => {
      const controller = new MockedLettaController(page);
      await controller.init();
      await controller.reset();
      await use(controller);
      await controller.dispose();
    },
    startConversation: async ({ mockedLetta }, use) => {
      await use((topic) => mockedLetta.startConversation(topic));
    },
    createSession: async ({ request }, use) => {
      await use((overrides) => createSessionViaApi(request, overrides));
    },
    listSessions: async ({ request }, use) => {
      await use((options) => listSessionsViaApi(request, options));
    },
    createSessionExport: async ({ request }, use) => {
      await use((sessionId) => createSessionExportViaApi(request, sessionId));
    },
    listSessionExports: async ({ request }, use) => {
      await use((sessionId, options) => listSessionExportsViaApi(request, sessionId, options));
    },
    setAgents: async ({ mockedLetta }, use) => {
      await use((agents) => mockedLetta.setAgents(agents));
    },
  }
);

export { expect } from '@playwright/test';
