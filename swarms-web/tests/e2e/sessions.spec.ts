import { expect, test, Page, Request } from '@playwright/test';

type SessionMeta = {
  id: string;
  title: string | null;
  created_at: string;
  last_updated: string;
  tags: string[];
};

type JsonResponse = {
  status: number;
  body: unknown;
};

const baseSessionTemplates: SessionMeta[] = [
  {
    id: 'session-1234567890',
    title: 'Strategy Sync',
    created_at: '2024-01-01T12:00:00Z',
    last_updated: '2024-01-02T09:15:00Z',
    tags: ['priority', 'swarm'],
  },
  {
    id: 'session-abcdef1234',
    title: 'Research Backlog',
    created_at: '2024-01-03T08:30:00Z',
    last_updated: '2024-01-04T16:45:00Z',
    tags: ['analysis'],
  },
];

const fulfillJson = (route: import('@playwright/test').Route, response: JsonResponse) =>
  route.fulfill({
    status: response.status,
    contentType: 'application/json',
    body: JSON.stringify(response.body),
  });

const parseJson = (request: Request) => {
  try {
    const fn = (request as any).postDataJSON;
    if (typeof fn === 'function') {
      const parsed = fn.call(request);
      return parsed ?? {};
    }
  } catch {
    /* fall through to manual parsing */
  }

  const data = request.postData();
  if (!data) return {};
  try {
    return JSON.parse(data);
  } catch {
    return {};
  }
};

const expectToast = async (page: Page, message: string) => {
  const toastContainer = page.locator('#toast-container');
  await expect(toastContainer, `Waiting for toast containing: ${message}`).toContainText(message);
};

test.describe('Session management lifecycle', () => {
  let sessions: SessionMeta[];
  let listResponseOverride: ((url: URL) => JsonResponse) | null;
  let createResponseOverride: ((payload: Record<string, unknown>) => JsonResponse) | null;
  let resumeResponseOverride: ((payload: Record<string, unknown>) => JsonResponse) | null;
  let createSequence: number;
  let sessionPrefix: string;

  const createRequests: Record<string, unknown>[] = [];
  test.beforeEach(async ({ page }, testInfo) => {
    const uniqueSuffix = [
      testInfo.workerIndex ?? 0,
      testInfo.parallelIndex ?? 0,
      testInfo.repeatEachIndex ?? 0,
      testInfo.retry ?? 0,
      Date.now().toString(36),
    ].join('-');

    sessionPrefix = `test-sess-A-${uniqueSuffix}`;

    sessions = baseSessionTemplates.map((session, index) => ({
      ...session,
      id: `${sessionPrefix}-${String(index + 1).padStart(2, '0')}`,
      tags: [...session.tags],
    }));
    listResponseOverride = null;
    createResponseOverride = null;
    resumeResponseOverride = null;
    createRequests.length = 0;
    createSequence = 0;

    await page.addInitScript(() => {
      class BootstrapToastStub {
        element: HTMLElement;

        constructor(element: HTMLElement) {
          this.element = element;
          setTimeout(() => {
            const shownEvent = new CustomEvent('shown.bs.toast');
            this.element.dispatchEvent(shownEvent);
          }, 0);
        }

        show() {
          setTimeout(() => {
            const hiddenEvent = new CustomEvent('hidden.bs.toast');
            this.element.dispatchEvent(hiddenEvent);
          }, 350);
        }
      }

      const ensureBootstrap = () => {
        const win = window as typeof window & {
          bootstrap?: { Toast: typeof BootstrapToastStub };
        };

        if (!win.bootstrap) {
          win.bootstrap = { Toast: BootstrapToastStub };
        }
      };

      ensureBootstrap();

      const win = window as typeof window & {
        io?: () => unknown;
        __PLAYWRIGHT_TEST?: string;
      };

      try {
        localStorage.clear();
        sessionStorage.clear();
      } catch (storageError) {
        console.warn('Unable to reset storage in init script', storageError);
      }

      win.io = () => ({
        on() {
          return this;
        },
        off() {
          return this;
        },
        emit() {
          return this;
        },
        disconnect() {
          /* noop */
        },
      });

      win.__PLAYWRIGHT_TEST = '1';
    });

    await page.route('**/socket.io.min.js*', async (route) => {
      await route.fulfill({
        contentType: 'application/javascript',
        body: 'window.io = window.io || (function(){ return function(){ return { on(){return this;}, off(){return this;}, emit(){return this;}, disconnect(){}, }; };})();',
      });
    });

    await page.route('**/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js*', async (route) => {
      await route.fulfill({
        contentType: 'application/javascript',
        body: 'window.bootstrap = window.bootstrap || { Toast: function Toast(){ this.show = function(){}; } };',
      });
    });

    await page.route('**/alpinejs@3.13.1/dist/cdn.min.js*', async (route) => {
      await route.fulfill({
        contentType: 'application/javascript',
        body: 'window.Alpine = window.Alpine || { start(){ /* noop */ } };',
      });
    });
    await page.route('**/api/sessions*', async (route) => {
      const request = route.request();

      if (request.method() === 'HEAD' || request.method() === 'OPTIONS') {
        await route.fulfill({ status: 204 });
        return;
      }

      if (request.method() === 'GET') {
        const handler = listResponseOverride
          ? listResponseOverride
          : (url: URL): JsonResponse => {
              const limitParam = url.searchParams.get('limit');
              let items = sessions;
              if (limitParam) {
                const limit = Number(limitParam);
                if (Number.isFinite(limit) && limit > 0) {
                  items = sessions.slice(0, limit);
                }
              }

              return { status: 200, body: items };
            };

        const url = new URL(request.url());
        const response = handler(url);
        await fulfillJson(route, response);
        return;
      }

      if (request.method() === 'POST') {
        const payload = parseJson(request);
        createRequests.push(payload);

        const handler = createResponseOverride
          ? createResponseOverride
          : (body: Record<string, unknown>): JsonResponse => {
              const nowIso = '2024-02-01T10:00:00Z';
              createSequence += 1;
              const newSessionId = `${sessionPrefix}-created-${String(createSequence).padStart(4, '0')}`;
              const newSession: SessionMeta = {
                id: newSessionId,
                title: typeof body.title === 'string' && body.title.trim() !== '' ? body.title : null,
                created_at: nowIso,
                last_updated: nowIso,
                tags: Array.isArray(body.tags) ? (body.tags as string[]) : [],
              };

              sessions = [newSession, ...sessions];
              return { status: 201, body: newSession };
            };

        const response = handler(payload);
        await fulfillJson(route, response);
        return;
      }

      await route.continue();
    });

    await page.route('**/api/sessions/resume', async (route) => {
      const request = route.request();
      const payload = parseJson(request);

      const handler = resumeResponseOverride
        ? resumeResponseOverride
        : (body: Record<string, unknown>): JsonResponse => {
            const sessionId = typeof body.id === 'string' ? body.id : '';
            const sessionExists = sessions.some((session) => session.id === sessionId);

            if (!sessionId) {
              return { status: 400, body: { error: 'id is required' } };
            }

            if (!sessionExists) {
              return { status: 404, body: { ok: false, error: 'not_found' } };
            }

            return { status: 200, body: { ok: true, id: sessionId } };
          };

      const response = handler(payload);
      await fulfillJson(route, response);
    });
  });

  test('renders existing sessions with key metadata', async ({ page }) => {
    await page.goto('/sessions');

    const rows = page.locator('tbody#sessions-table-body tr.session-row');
    await expect(rows).toHaveCount(2);

    await expect(rows.nth(0)).toContainText('Strategy Sync');
    await expect(rows.nth(0)).toContainText('priority');
    await expect(rows.nth(1)).toContainText('Research Backlog');
    await expect(rows.nth(1)).toContainText('analysis');
  });

  test('shows the empty state when no sessions exist', async ({ page }) => {
    sessions = [];

    await page.goto('/sessions');

    await expect(page.locator('#loading-spinner')).toBeHidden();
    await expect(page.locator('#empty-state')).toBeVisible();
    await expect(page.locator('#sessions-container').locator('table')).toHaveCount(0);
  });

  test('respects limit query parameter when listing sessions', async ({ page }) => {
    await page.goto('/sessions');

    const items = await page.evaluate<SessionMeta[]>(async () => {
      const response = await fetch('/api/sessions?limit=1');
      if (!response.ok) {
        throw new Error(`Unexpected status: ${response.status}`);
      }

      return (await response.json()) as SessionMeta[];
    });

    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      ...baseSessionTemplates[0],
      id: `${sessionPrefix}-01`,
    });
  });

  test('surfaces backend errors when loading sessions fails', async ({ page }) => {
    listResponseOverride = () => ({ status: 500, body: { error: 'cannot list sessions' } });

    await page.goto('/sessions');

    await expectToast(page, 'Error loading sessions: cannot list sessions');
  });

  test('creates a new session, stores context, and redirects to chat', async ({ page }) => {
    const expectedSessionId = `${sessionPrefix}-created-0001`;
    const chatVisits: string[] = [];

    await page.route('**/chat*', async (route) => {
      chatVisits.push(route.request().url());
      await route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: '<html><body><div id="chat-placeholder">Chat page ready</div></body></html>',
      });
    });

    await page.goto('/sessions');

    const rows = page.locator('tbody#sessions-table-body tr.session-row');
    await expect(rows).toHaveCount(2);

    await page.locator('#session-title').fill('Product Planning');
    await page.locator('#session-tags').fill('planning, roadmap');

    const navigationPromise = page.waitForURL(`**/chat?sessionId=${expectedSessionId}`);

    await page.locator('#new-session-form button[type="submit"]').click();

    await expectToast(page, 'Session created successfully!');
    await navigationPromise;

    await expect(page.locator('#chat-placeholder')).toContainText('Chat page ready');

    const storedSessionId = await page.evaluate(() => sessionStorage.getItem('sessionId'));
    expect(storedSessionId).toBe(expectedSessionId);

    const storedTopic = await page.evaluate(() => sessionStorage.getItem('topic'));
    expect(storedTopic).toBe('Product Planning');

    expect(chatVisits).toHaveLength(1);
    expect(chatVisits[0]).toContain(`sessionId=${expectedSessionId}`);

    expect(createRequests).toHaveLength(1);
    expect(createRequests[0]).toMatchObject({
      title: 'Product Planning',
      tags: ['planning', 'roadmap'],
    });
  });

  test('lists sessions, creates a new one, and resumes another into chat', async ({ page }) => {
    const createdSessionId = `${sessionPrefix}-created-0001`;
    const resumedSessionId = `${sessionPrefix}-01`;
    const chatVisits: string[] = [];

    await page.route('**/chat*', async (route) => {
      chatVisits.push(route.request().url());
      await route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: '<html><body><div id="chat-placeholder">Chat ready</div></body></html>',
      });
    });

    await page.goto('/sessions');

    const initialRows = page.locator('tbody#sessions-table-body tr.session-row');
    await expect(initialRows).toHaveCount(2);
    await expect(initialRows.nth(0)).toContainText('Strategy Sync');
    await expect(initialRows.nth(1)).toContainText('Research Backlog');

    const createNavigation = page.waitForURL(`**/chat?sessionId=${createdSessionId}`);

    await page.locator('#session-title').fill('Lifecycle Flow Session');
    await page.locator('#session-tags').fill('flow, playwright');
    await page.locator('#new-session-form button[type="submit"]').click();

    await expectToast(page, 'Session created successfully!');
    await createNavigation;

    expect(chatVisits).toHaveLength(1);
    expect(chatVisits[0]).toContain(`sessionId=${createdSessionId}`);

    await page.goto('/sessions');

    const updatedRows = page.locator('tbody#sessions-table-body tr.session-row');
    await expect(updatedRows).toHaveCount(3);
    await expect(updatedRows.first()).toContainText('Lifecycle Flow Session');
    await expect(updatedRows.nth(1)).toContainText('Strategy Sync');

    const resumeNavigation = page.waitForURL(`**/chat?sessionId=${resumedSessionId}`);

    await updatedRows.nth(1).locator('button.resume-session').click();

    await expectToast(page, 'Session resumed successfully!');
    await resumeNavigation;

    expect(chatVisits).toHaveLength(2);
    expect(chatVisits[1]).toContain(`sessionId=${resumedSessionId}`);

    const storedSessionId = await page.evaluate(() => sessionStorage.getItem('sessionId'));
    expect(storedSessionId).toBe(resumedSessionId);
  });

  test('shows validation errors returned from create session endpoint', async ({ page }) => {
    createResponseOverride = () => ({ status: 400, body: { error: 'tags must be an array' } });

    await page.goto('/sessions');

    await page.locator('#session-title').fill('Invalid Payload');
    await page.locator('#session-tags').fill('should,fail');
    await page.locator('#new-session-form button[type="submit"]').click();

    await expectToast(page, 'Error creating session: tags must be an array');
    await expect(page.locator('tbody#sessions-table-body tr.session-row')).toHaveCount(2);
  });

  test('handles malformed create payload response', async ({ page }) => {
    createResponseOverride = () => ({ status: 400, body: { error: 'Invalid JSON payload' } });

    await page.goto('/sessions');

    await page.locator('#new-session-form button[type="submit"]').click();

    await expectToast(page, 'Error creating session: Invalid JSON payload');
  });

  test('resumes a session successfully and redirects to chat', async ({ page }) => {
    const resumedSessionId = `${sessionPrefix}-01`;
    const chatVisits: string[] = [];

    await page.route('**/chat*', async (route) => {
      chatVisits.push(route.request().url());
      await route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: '<html><body><div id="chat-placeholder">Chat page</div></body></html>',
      });
    });

    resumeResponseOverride = (payload) => ({
      status: 200,
      body: { ok: true, id: payload.id },
    });

    await page.goto('/sessions');

    const navigationPromise = page.waitForURL(`**/chat?sessionId=${resumedSessionId}`);

    await page.locator('button.resume-session').first().click();

    await expectToast(page, 'Session resumed successfully!');
    await navigationPromise;

    expect(chatVisits).toHaveLength(1);
    expect(chatVisits[0]).toContain(`sessionId=${resumedSessionId}`);

    const storedSessionId = await page.evaluate(() => sessionStorage.getItem('sessionId'));
    expect(storedSessionId).toBe(resumedSessionId);
  });

  test('shows message when attempting to resume without providing an ID', async ({ page }) => {
    resumeResponseOverride = () => ({ status: 400, body: { error: 'id is required' } });

    await page.goto('/sessions');

    await page.locator('button.resume-session').first().click();

    await expectToast(page, 'Error resuming session: id is required');
    await expect(page).not.toHaveURL('**/chat*', { timeout: 2000 });
    await expect(page).toHaveURL(/\/sessions(\?.*)?$/);
  });

  test('surfaces not found errors when resuming unknown sessions', async ({ page }) => {
    resumeResponseOverride = () => ({ status: 404, body: { ok: false, error: 'not_found' } });

    await page.goto('/sessions');

    await page.locator('button.resume-session').first().click();

    await expectToast(page, 'Error resuming session: Session not found');
    await expect(page).not.toHaveURL('**/chat*', { timeout: 2000 });
    await expect(page).toHaveURL(/\/sessions(\?.*)?$/);
  });

  test('shows server error messages when resume fails unexpectedly', async ({ page }) => {
    resumeResponseOverride = () => ({ status: 500, body: { error: 'boom' } });

    await page.goto('/sessions');

    await page.locator('button.resume-session').first().click();

    await expectToast(page, 'Error resuming session: boom');
    await expect(page).not.toHaveURL('**/chat*', { timeout: 2000 });
    await expect(page).toHaveURL(/\/sessions(\?.*)?$/);
  });

  test('refreshes the list to reflect deleted sessions', async ({ page }) => {
    await page.goto('/sessions');

    const rows = page.locator('tbody#sessions-table-body tr.session-row');
    await expect(rows).toHaveCount(2);

    sessions = [sessions[1]];

    await page.locator('#refresh-sessions').click();

    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText('Research Backlog');
    await expect(rows.first()).not.toContainText('Strategy Sync');
  });
});
