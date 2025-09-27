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
type EmitSocketEventFn = (event: string, payload?: unknown) => Promise<void>;
type SetAgentResponseFn = (response: string) => Promise<void>;

const defaultSessionPayload = (): Required<CreateSessionPayload> => ({
  title: 'Playwright Session',
  tags: ['playwright'],
});

/**
 * Creates a session via the test API and returns its summary.
 *
 * The provided `overrides` are shallow-merged with the test `defaultSessionPayload`.
 * The function asserts that the HTTP response is OK (will fail the test if not) and
 * returns the parsed SessionSummary from the response body.
 *
 * @param overrides - Optional fields (e.g., `title`, `tags`) to override the default session payload.
 * @returns The created session's summary as a `SessionSummary`.
 */
async function createSessionViaApi(
  request: APIRequestContext,
  overrides: CreateSessionPayload | undefined
): Promise<SessionSummary> {
  const payload = { ...defaultSessionPayload(), ...overrides };
  const response = await request.post('/api/sessions', { data: payload });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as SessionSummary;
}

/**
 * Fetches sessions from the server API and returns them as SessionSummary objects.
 *
 * Sends a GET request to `/api/sessions` with an optional `limit` query parameter,
 * asserts that the HTTP response is OK (test assertion), and returns the parsed JSON array.
 *
 * @param options - Optional settings:
 *   - `limit`: maximum number of sessions to return; if omitted the server default is used.
 * @returns An array of SessionSummary objects parsed from the response.
 * @throws If the HTTP response is not OK — the function asserts `response.ok()` and will fail the test.
 */
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

/**
 * Creates an export for a session via the API.
 *
 * Sends a POST to `/api/sessions/{sessionId}/export` and returns the parsed
 * CreateExportResponse from the server. The function asserts that the HTTP
 * response is OK — the assertion will fail the calling test if the request
 * does not succeed.
 *
 * @param sessionId - ID of the session to export
 * @returns The server's CreateExportResponse object
 */
async function createSessionExportViaApi(
  request: APIRequestContext,
  sessionId: string
): Promise<CreateExportResponse> {
  const response = await request.post(`/api/sessions/${sessionId}/export`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as CreateExportResponse;
}

/**
 * Retrieve the list of exports for a session via the API.
 *
 * @param sessionId - ID of the session whose exports should be listed.
 * @param options - Optional query options.
 * @param options.limit - Maximum number of exports to return.
 * @returns An array of SessionExport objects for the given session.
 */
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
  emitSocketEvent: EmitSocketEventFn;
  setAgentResponse: SetAgentResponseFn;
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
    emitSocketEvent: async ({ page }, use) => {
      await use(async (event, payload) => {
        await page.evaluate(
          ([eventName, eventPayload]) => {
            const win = window as typeof window & {
              __playwrightEmitSocketEvent?: (name: string, data?: unknown) => void;
              __TEST_EMIT?: (name: string, data?: unknown) => void;
            };

            if (typeof win.__playwrightEmitSocketEvent === 'function') {
              win.__playwrightEmitSocketEvent(eventName, eventPayload);
              return;
            }

            if (typeof win.__TEST_EMIT === 'function') {
              win.__TEST_EMIT(eventName, eventPayload);
              return;
            }

            // eslint-disable-next-line no-console
            console.error('Socket emit hooks not found on window');
          },
          [event, payload] as const
        );
      });
    },
    setAgentResponse: async ({ mockedLetta }, use) => {
      await use((response) => mockedLetta.setAgentResponse(response));
    },
  }
);

export { expect } from '@playwright/test';
