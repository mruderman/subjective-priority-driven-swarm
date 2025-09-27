import { expect, test, Page } from '@playwright/test';

type SessionMeta = {
  id: string;
  title: string | null;
  created_at: string;
  last_updated: string;
  tags: string[];
};

type SessionExport = {
  filename: string;
  size_bytes: number;
  created_at: string;
  kind: 'json' | 'markdown';
};

const installBootstrapToastStub = async (page: Page) => {
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

    const win = window as typeof window & {
      bootstrap?: { Toast?: typeof BootstrapToastStub };
    };

    if (!win.bootstrap) {
      win.bootstrap = { Toast: BootstrapToastStub };
      return;
    }

    win.bootstrap.Toast = BootstrapToastStub;
  });

  await page.route('**/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js*', async (route) => {
    await route.fulfill({
      contentType: 'application/javascript',
      body: 'window.bootstrap = window.bootstrap || { Toast: function Toast(){ this.show = function(){}; } };',
    });
  });
};

const installSocketStub = async (page: Page) => {
  await page.addInitScript(() => {
    const socketApi = {
      on() {
        return socketApi;
      },
      off() {
        return socketApi;
      },
      emit() {
        return socketApi;
      },
      disconnect() {
        /* noop */
      },
    };

    const win = window as typeof window & { io?: () => typeof socketApi };
    win.io = () => socketApi;
  });

  await page.route('**/socket.io.min.js*', async (route) => {
    await route.fulfill({
      contentType: 'application/javascript',
      body: 'window.io = window.io || (function(){ return function(){ return { on(){return this;}, off(){return this;}, emit(){return this;}, disconnect(){} }; };})();',
    });
  });
};

const expectToast = async (page: Page, message: string | RegExp) => {
  const toastContainer = page.locator('#toast-container');
  await expect(toastContainer).toContainText(message);
};

test.describe('Resilient UI error handling', () => {
  test('recovers from a failed sessions list request with a manual retry', async ({ page }) => {
    await installBootstrapToastStub(page);

    const sessions: SessionMeta[] = [
      {
        id: 'session-retry-001',
        title: 'Retry Strategy',
        created_at: '2024-03-01T10:00:00Z',
        last_updated: '2024-03-02T09:15:00Z',
        tags: ['operations'],
      },
    ];

    let sessionsCallCount = 0;
    await page.route('**/api/sessions', async (route) => {
      const request = route.request();
      if (request.method() !== 'GET') {
        await route.continue();
        return;
      }

      sessionsCallCount += 1;
      if (sessionsCallCount === 1) {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Simulated server failure' }),
        });
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(sessions),
      });
    });

    await page.goto('/sessions');

    await expectToast(page, 'Error loading sessions: Simulated server failure');
    await expect(page.locator('#loading-spinner')).toBeHidden();

    const refreshButton = page.locator('#refresh-sessions');
    await expect(refreshButton).toBeEnabled();

    await test.step('Retry fetch succeeds and hydrates the table', async () => {
      await refreshButton.click();

      const rows = page.locator('#sessions-table-body tr.session-row');
      await expect(rows).toHaveCount(1);
      await expect(rows.first()).toContainText('Retry Strategy');
      await expect(page.locator('#loading-spinner')).toBeHidden();
    });
  });

  test('allows retrying an attachment upload after a network failure', async ({ page }) => {
    await installBootstrapToastStub(page);
    await installSocketStub(page);

    const sessionId = 'retry-attachments-session';
    await page.addInitScript((id) => {
      try {
        sessionStorage.setItem('sessionId', id);
        sessionStorage.setItem('topic', 'Network resilience run');
      } catch (error) {
        /* ignore */
      }
    }, sessionId);

    let messageAttempts = 0;
    await page.route('**/api/messages', async (route) => {
      messageAttempts += 1;

      if (messageAttempts === 1) {
        await route.abort('failed');
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, attachments_count: 1 }),
      });
    });

    await page.goto(`/chat?session_id=${sessionId}`);

    await page.waitForFunction(() => Boolean((window as typeof window & { simpleChat?: unknown }).simpleChat));

    const injectAttachment = async () => {
      await page.evaluate(() => {
        const chat = (window as typeof window & { simpleChat?: { pendingAttachments: unknown[] } }).simpleChat;
        if (!chat) {
          return;
        }

        chat.pendingAttachments = [
          {
            filename: 'status-report.pdf',
            mime: 'application/pdf',
            kind: 'document',
            size_bytes: 2048,
            url: '/uploads/status-report.pdf',
          },
        ];
      });
    };

    const sendButton = page.locator('#send-button');

    await injectAttachment();
    await sendButton.click();

    await expectToast(page, /Failed to send message:/);
    await expect(sendButton).toBeEnabled();
    await expect(page.locator('#attachment-preview')).toBeHidden();

    await test.step('Retry sending succeeds after the transient failure', async () => {
      await injectAttachment();
      await sendButton.click();

      await expectToast(page, 'Message sent with 1 attachment(s)');
      await expect(sendButton).toBeEnabled();
    });
  });

  test('recovers when secretary exports initially fail', async ({ page }) => {
    await installBootstrapToastStub(page);

    const sessionId = 'session-export-retry';
    const sessions: SessionMeta[] = [
      {
        id: sessionId,
        title: 'Secretary Export Recovery',
        created_at: '2024-03-05T14:00:00Z',
        last_updated: '2024-03-06T16:30:00Z',
        tags: ['minutes'],
      },
    ];

    let exportsReady = false;
    let exportAttempts = 0;

    await page.route('**/api/sessions', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.continue();
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(sessions),
      });
    });

    await page.route(`**/api/sessions/${sessionId}/exports`, async (route) => {
      const payload: SessionExport[] = exportsReady
        ? [
            {
              filename: 'secretary-minutes.md',
              kind: 'markdown',
              created_at: '2024-03-06T17:00:00Z',
              size_bytes: 4096,
            },
          ]
        : [];

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(payload),
      });
    });

    await page.route(`**/api/sessions/${sessionId}/export`, async (route) => {
      exportAttempts += 1;

      if (exportAttempts === 1) {
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Secretary service unavailable' }),
        });
        return;
      }

      exportsReady = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      });
    });

    await page.goto('/sessions');

    const viewExportsButton = page.locator(`button.view-exports[data-id="${sessionId}"]`).first();
    await viewExportsButton.click();

    const createFirstExport = page.locator('#create-first-export');
    await expect(createFirstExport).toBeVisible();
    await expect(createFirstExport).toBeEnabled();

    await createFirstExport.click();

    await expectToast(page, 'Error exporting session: Secretary service unavailable');
    await expect(createFirstExport).toBeEnabled();
    await expect(page.locator('#exports-loading')).toBeHidden();

    await test.step('Retry export produces downloadable artifacts', async () => {
      await createFirstExport.click();

      await expectToast(page, 'Session exported successfully!');

      const exportItems = page.locator('#exports-container .export-item');
      await expect(exportItems).toHaveCount(1);
      await expect(exportItems.first()).toContainText('secretary-minutes.md');
      await expect(page.locator('#exports-loading')).toBeHidden();
    });
  });
});
