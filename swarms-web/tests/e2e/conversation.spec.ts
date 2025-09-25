import { expect, test, Page } from '@playwright/test';

type MockAgent = {
  id: string;
  name: string;
  model: string;
  created_at: string;
};

const mockAgents: MockAgent[] = [
  {
    id: 'agent-1',
    name: 'Alex Johnson',
    model: 'openai/gpt-4',
    created_at: '2024-01-01',
  },
  {
    id: 'agent-2',
    name: 'Jordan Smith',
    model: 'anthropic/claude-3',
    created_at: '2024-01-02',
  },
  {
    id: 'agent-3',
    name: 'Casey Lee',
    model: 'openai/gpt-4',
    created_at: '2024-01-03',
  },
];

const exportFixtures = {
  formal: 'exports/board_minutes_formal.md',
  casual: 'exports/meeting_notes_casual.md',
  transcript: 'exports/conversation_transcript.txt',
  actions: 'exports/action_items.md',
  summary: 'exports/executive_summary.md',
  data: 'exports/structured_data.json',
  all: [
    'exports/board_minutes_formal.md',
    'exports/meeting_notes_casual.md',
    'exports/conversation_transcript.txt',
    'exports/action_items.md',
    'exports/executive_summary.md',
    'exports/structured_data.json',
  ],
} as const;

let currentAgents: MockAgent[] = [...mockAgents];

test.beforeEach(async ({ page }) => {
  currentAgents = [...mockAgents];

  await page.addInitScript(({ agents, exports: exportData }) => {
    const mockAgentsData = agents as MockAgent[];
    const exportFixturesData = exportData as Record<string, unknown>;

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
        }, 1500);
      }
    }

    class BootstrapModalStub {
      element: HTMLElement;

      constructor(element: HTMLElement) {
        this.element = element;
        (this.element as { __modalInstance?: BootstrapModalStub }).__modalInstance = this;
      }

      show() {
        this.element.classList.add('show');
        this.element.style.display = 'block';
        this.element.removeAttribute('aria-hidden');
      }

      hide() {
        this.element.classList.remove('show');
        this.element.style.display = 'none';
        this.element.setAttribute('aria-hidden', 'true');
      }

      static getInstance(element: HTMLElement) {
        return (element as { __modalInstance?: BootstrapModalStub }).__modalInstance ?? null;
      }

      static getOrCreateInstance(element: HTMLElement) {
        return (
          (element as { __modalInstance?: BootstrapModalStub }).__modalInstance ??
          new BootstrapModalStub(element)
        );
      }
    }

    const ensureBootstrap = () => {
      const win = window as typeof window & {
        bootstrap?: {
          Toast?: typeof BootstrapToastStub;
          Modal?: typeof BootstrapModalStub;
        };
      };

      if (!win.bootstrap) {
        win.bootstrap = { Toast: BootstrapToastStub, Modal: BootstrapModalStub };
        return;
      }

      if (!win.bootstrap.Toast) {
        win.bootstrap.Toast = BootstrapToastStub;
      }
      if (!win.bootstrap.Modal) {
        win.bootstrap.Modal = BootstrapModalStub;
      }
    };

    const createSocketFactory = () => {
      type Listener = (payload?: unknown) => void;
      type SocketAPI = {
        on: (event: string, callback: Listener) => SocketAPI;
        off: (event?: string) => SocketAPI;
        emit: (event: string, payload?: Record<string, unknown>) => SocketAPI;
        disconnect: () => void;
      };

      let socket: SocketAPI | null = null;

      const factory = () => {
        if (socket) {
          return socket;
        }

        const listeners = new Map<string, Listener[]>();

        const ensureListeners = (event: string) => {
          if (!listeners.has(event)) {
            listeners.set(event, []);
          }
          return listeners.get(event)!;
        };

        const emitEvent = (event: string, payload?: unknown) => {
          const handlers = listeners.get(event);
          if (!handlers) {
            return;
          }
          handlers.forEach((handler) => {
            try {
              handler(payload);
            } catch (error) {
              console.error('Mock socket handler error', error);
            }
          });
        };

        const api: SocketAPI = {
          on(event: string, callback: Listener) {
            ensureListeners(event).push(callback);
            if (event === 'connect') {
              setTimeout(() => callback(undefined), 0);
            }
            return api;
          },
          off(event?: string) {
            if (!event) {
              listeners.clear();
            } else {
              listeners.delete(event);
            }
            return api;
          },
          emit(event: string, payload?: Record<string, unknown>) {
            if (event === 'join_session' && payload?.session_id) {
              setTimeout(() => emitEvent('joined', { session_id: payload.session_id }), 0);
            }

            if (event === 'start_chat' && payload?.topic) {
              setTimeout(() => {
                emitEvent('chat_started', {
                  topic: payload.topic,
                  mode: 'hybrid',
                  agents: mockAgentsData.map((agent: MockAgent) => ({ name: agent.name, id: agent.id })),
                  secretary_enabled: true,
                });
              }, 50);
            }

            if (event === 'user_message' && typeof payload?.message === 'string') {
              const message = payload.message;
              const timestamp = new Date().toISOString();

              setTimeout(() => {
                emitEvent('user_message', {
                  speaker: 'You',
                  message,
                  timestamp,
                });
              }, 0);

              const trimmedMessage = message.trim();
              if (trimmedMessage.startsWith('/')) {
                const command = trimmedMessage.split(/\s+/)[0];
                switch (command) {
                  case '/minutes':
                    setTimeout(() => {
                      const minutesContainer = document.getElementById('secretary-minutes');
                      if (minutesContainer) {
                        minutesContainer.style.display = 'block';
                      }
                      emitEvent('secretary_activity', {
                        activity: 'generating',
                        message: '📝 Generating meeting minutes...',
                      });
                      emitEvent('secretary_minutes', {
                        minutes: 'Meeting Minutes\n- Agenda review\n- Decisions recorded',
                      });
                      emitEvent('secretary_activity', {
                        activity: 'completed',
                        message: '✅ Meeting minutes generated!',
                      });
                    }, 120);
                    break;
                  case '/stats':
                    setTimeout(() => {
                      emitEvent('secretary_activity', {
                        activity: 'generating',
                        message: '📊 Gathering conversation statistics...',
                      });
                      emitEvent('secretary_stats', {
                        stats: {
                          'Total Messages': 12,
                          'Agents Responded': '2 / 3',
                          'Action Items Logged': 3,
                        },
                      });
                      emitEvent('secretary_activity', {
                        activity: 'completed',
                        message: '📈 Conversation stats are ready!',
                      });
                    }, 120);
                    break;
                  case '/formal':
                  case '/casual': {
                    const mode = command.slice(1);
                    setTimeout(() => {
                      emitEvent('secretary_status', {
                        status: 'active',
                        agent_name: 'Avery Secretary',
                        mode,
                        message:
                          mode === 'formal'
                            ? 'Secretary switched to formal minutes mode.'
                            : 'Secretary switched to casual notes mode.',
                      });
                    }, 80);
                    break;
                  }
                  case '/export': {
                    const parts = trimmedMessage.split(/\s+/, 2);
                    const requestedFormat = (parts[1] || 'formal').toLowerCase();
                    const normalizedFormat =
                      requestedFormat === 'minutes' ? 'formal' : requestedFormat;

                    setTimeout(() => {
                      if (
                        normalizedFormat === 'all' &&
                        Array.isArray(exportFixturesData.all)
                      ) {
                        const allFiles = exportFixturesData.all as unknown[];
                        const formats = allFiles.map((filePath) => {
                          if (typeof filePath !== 'string') {
                            return 'unknown';
                          }

                          const matchedEntry = Object.entries(exportFixturesData).find(
                            ([key, value]) => {
                              if (key === 'all') {
                                return false;
                              }

                              if (typeof value === 'string') {
                                return value === filePath;
                              }

                              if (Array.isArray(value)) {
                                return value.includes(filePath);
                              }

                              if (value && typeof value === 'object') {
                                const typed = value as { path?: string; filename?: string };
                                return typed.path === filePath || typed.filename === filePath;
                              }

                              return false;
                            }
                          );

                          return matchedEntry?.[0] ?? 'unknown';
                        });

                        emitEvent('export_complete', {
                          files: exportFixturesData.all,
                          formats,
                          count: allFiles.length,
                        });
                      } else {
                        const fixture =
                          exportFixturesData[normalizedFormat] ??
                          exportFixturesData.formal;

                        if (typeof fixture === 'string') {
                          emitEvent('export_complete', {
                            file: fixture,
                            format: normalizedFormat,
                          });
                        } else if (Array.isArray(fixture)) {
                          emitEvent('export_complete', {
                            files: fixture,
                            count: fixture.length,
                          });
                        } else if (fixture && typeof fixture === 'object') {
                          const typedFixture = fixture as { path?: string; filename?: string };
                          const pathValue = typedFixture.path ?? typedFixture.filename;
                          emitEvent('export_complete', {
                            file: pathValue ?? `exports/${normalizedFormat}.md`,
                            format: normalizedFormat,
                          });
                        } else {
                          emitEvent('export_complete', {
                            file: `exports/${normalizedFormat}_mock.txt`,
                            format: normalizedFormat,
                          });
                        }
                      }
                    }, 80);
                    break;
                  }
                  case '/memory-status':
                    setTimeout(() => {
                      emitEvent('secretary_status', {
                        status: 'awareness',
                        agent_name: 'Memory Monitor',
                        mode: 'memory tracking',
                        message: 'Memory status summarized for 3 agents.',
                      });
                    }, 80);
                    break;
                  case '/memory-awareness':
                    setTimeout(() => {
                      emitEvent('secretary_status', {
                        status: 'insight',
                        agent_name: 'Memory Monitor',
                        mode: 'awareness check',
                        message: 'Agents notified about recent memory usage.',
                      });
                    }, 80);
                    break;
                  case '/help':
                    setTimeout(() => {
                      emitEvent('system_message', {
                        message: [
                          '📝 Available Commands:',
                          '',
                          'Memory Awareness (Available Always):',
                          '  /memory-status     - Show objective memory statistics for all agents',
                          '  /memory-awareness  - Display neutral memory awareness information if criteria are met',
                          '',
                          'Secretary Commands (When Secretary Enabled):',
                          '  /minutes           - Generate current meeting minutes',
                          '  /stats             - Show conversation statistics',
                          '',
                          'General:',
                          '  /help              - Show this help message',
                        ].join('\\n'),
                        timestamp: new Date().toISOString(),
                      });
                    }, 60);
                    break;
                  default:
                    setTimeout(() => {
                      emitEvent('system_message', {
                        message: `Unrecognized command: ${trimmedMessage}`,
                        timestamp: new Date().toISOString(),
                      });
                    }, 40);
                    break;
                }
              } else {
                setTimeout(() => {
                  emitEvent('agent_message', {
                    speaker: mockAgentsData[0]?.name || 'Agent',
                    message: 'AI advancements look promising with collaborative intelligence.',
                    timestamp: new Date().toISOString(),
                    phase: 'response',
                  });
                }, 150);
              }
            }

            return api;
          },
          disconnect() {
            listeners.clear();
          },
        };

        socket = api;
        return api;
      }

      return factory;
    };

    ensureBootstrap();

    const win = window as typeof window & {
      __playwrightCreateSocketIO?: () => () => unknown;
      io?: () => unknown;
      __PLAYWRIGHT_TEST?: string;
    };

    win.__playwrightCreateSocketIO = createSocketFactory;
    const socketFactory = createSocketFactory();
    win.io = () => socketFactory();
  }, { agents: mockAgents, exports: exportFixtures });

  await page.route('**/socket.io.min.js*', async (route) => {
    await route.fulfill({
      contentType: 'application/javascript',
      body: 'window.io = window.io || (window.__playwrightCreateSocketIO && window.__playwrightCreateSocketIO());',
    });
  });

  await page.route('**/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js*', async (route) => {
    await route.fulfill({
      contentType: 'application/javascript',
      body: `
        (function(){
          if (!window.bootstrap) {
            const toastStub = function ToastStub(element) {
              this.element = element;
            };
            toastStub.prototype.show = function show() {};

            class ModalStub {
              constructor(element) {
                this.element = element;
                ModalStub._instances.set(element, this);
              }

              show() {
                this.element.classList.add('show');
                this.element.style.display = 'block';
                this.element.removeAttribute('aria-hidden');
              }

              hide() {
                this.element.classList.remove('show');
                this.element.style.display = 'none';
                this.element.setAttribute('aria-hidden', 'true');
              }

              static getInstance(element) {
                return ModalStub._instances.get(element) || null;
              }

              static getOrCreateInstance(element) {
                return ModalStub.getInstance(element) || new ModalStub(element);
              }
            }

            ModalStub._instances = new WeakMap();

            window.bootstrap = { Toast: toastStub, Modal: ModalStub };
          }
        })();
      `,
    });
  });

  await page.route('**/api/agents', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ agents: currentAgents }),
    });
  });

  // Inject a browser-global flag and set sessionStorage early to avoid
  // evaluate/navigation races. Harmless when running locally.
  await page.addInitScript(() => {
    (window as any).__PLAYWRIGHT_TEST = '1';
    try {
      sessionStorage.setItem('sessionId', 'session-test');
    } catch (e) {
      // ignore
    }
  });
});

const startConversation = async (page: Page, topic = 'Exploring AI collaboration') => {
  await page.goto('/setup');

  const agentCards = page.locator('.agent-card');
  await expect(agentCards.first()).toBeVisible();

  await agentCards.nth(0).locator('input.agent-checkbox').check();
  await agentCards.nth(1).locator('input.agent-checkbox').check();

  await page.locator('.mode-card').first().click();
  await page.locator('#topic').fill(topic);

  await page.locator('#start-chat-btn').click();

  await page.waitForResponse('**/api/start_session');
  await expect(page.locator('#chat-input')).toBeVisible();
};

const sendSlashCommand = async (page: Page, command: string) => {
  await page.locator('#chat-input').fill(command);
  await page.locator('#send-button').click();
};

test('should load the main page and display agent selection cards', async ({ page }) => {
  await page.goto('/setup');

  await expect(page.getByText('Subjective Priority-Driven Swarm')).toBeVisible();
  await expect(page.locator('.agent-card').first()).toBeVisible();
});

test('should allow a user to select agents, start a chat, and see agent responses', async ({ page }) => {
  await startConversation(page, 'The future of AI collaboration');

  await page.locator('#chat-input').fill('What is the future of AI?');
  await page.locator('#send-button').click();

  const userMessage = page.locator('#chat-messages .message.user').filter({ hasText: 'What is the future of AI?' });
  await expect(userMessage).toHaveCount(1);

  const agentMessage = page.locator('#chat-messages .message.agent').first();
  await expect(agentMessage).toBeVisible();
  await expect(agentMessage.locator('.message-content')).not.toHaveText(/^\s*$/);
});

test('should respond to the /minutes slash command', async ({ page }) => {
  await startConversation(page, 'Documenting project updates');

  await sendSlashCommand(page, '/minutes');

  const minutesContent = page.locator('#secretary-minutes');
  await expect(minutesContent).toBeVisible();
  await expect(minutesContent).toContainText('Meeting Minutes');
});

test('should reveal secretary stats when using the /stats command', async ({ page }) => {
  await startConversation(page, 'Tracking meeting participation');

  await sendSlashCommand(page, '/stats');

  const statsContent = page.locator('#secretary-stats');
  await expect(statsContent).toBeVisible();
  await expect(statsContent).toContainText('Total Messages');
  await expect(statsContent).toContainText('Agents Responded');
});

test('should show a toast with memory status details for /memory-status', async ({ page }) => {
  await startConversation(page, 'Memory diagnostics conversation');

  await sendSlashCommand(page, '/memory-status');

  const toastContainer = page.locator('#toast-container');
  await expect(toastContainer).toContainText('Memory status summarized for 3 agents.');
});

test('should show a toast when /memory-awareness is triggered', async ({ page }) => {
  await startConversation(page, 'Memory awareness insights');

  await sendSlashCommand(page, '/memory-awareness');

  const toastContainer = page.locator('#toast-container');
  await expect(toastContainer).toContainText('Agents notified about recent memory usage.');
});

test('should surface help documentation after sending /help', async ({ page }) => {
  await startConversation(page, 'Reviewing secretary commands');

  await sendSlashCommand(page, '/help');

  const helpMessage = page
    .locator('#chat-messages .message.system')
    .filter({ hasText: 'Available Commands' });
  await expect(helpMessage).toHaveCount(1);
});

test('should display secretary options when the toggle is enabled', async ({ page }) => {
  await page.goto('/setup');

  const secretaryToggle = page.locator('#enable_secretary');
  const secretaryOptions = page.locator('#secretary-options');

  await expect(secretaryOptions).toBeHidden();

  await secretaryToggle.check();
  await expect(secretaryOptions).toBeVisible();

  await secretaryToggle.uncheck();
  await expect(secretaryOptions).toBeHidden();
});

test('should require selecting at least one agent before starting a session', async ({ page }) => {
  await page.goto('/setup');

  await expect(page.locator('.agent-card').first()).toBeVisible();

  await page.locator('#topic').fill('Valid topic without agent selection');
  await page.locator('#start-chat-btn').click();

  await expect(page.locator('#toast-container')).toContainText('Please select at least one agent');
});

test('should update conversation mode selection when cards are changed', async ({ page }) => {
  await page.goto('/setup');

  const hybridCard = page.locator('.mode-card[data-mode="hybrid"]');
  const allSpeakCard = page.locator('.mode-card[data-mode="all_speak"]');
  const modeInput = page.locator('#conversation_mode');

  await expect(hybridCard).toHaveClass(/selected/);
  await expect(modeInput).toHaveValue('hybrid');

  await allSpeakCard.click();

  await expect(allSpeakCard).toHaveClass(/selected/);
  await expect(hybridCard).not.toHaveClass(/selected/);
  await expect(modeInput).toHaveValue('all_speak');
});

test('should show a warning when no agents are returned from the server', async ({ page }) => {
  currentAgents = [];
  await page.goto('/setup');

  const noAgentsAlert = page.locator('#no-agents');
  await expect(noAgentsAlert).toBeVisible();
  await expect(page.locator('#agent-count')).toHaveText('None Available');
});

test('should trigger secretary exports and surface downloadable links', async ({ page }) => {
  await startConversation(page, 'Automated export verification');

  await page.route('**/exports/**', async (route) => {
    const requestUrl = new URL(route.request().url());
    const filename = decodeURIComponent(requestUrl.pathname.split('/').pop() || 'export.txt');

    let contentType = 'application/octet-stream';
    if (filename.endsWith('.md')) {
      contentType = 'text/markdown; charset=utf-8';
    } else if (filename.endsWith('.txt')) {
      contentType = 'text/plain; charset=utf-8';
    } else if (filename.endsWith('.json')) {
      contentType = 'application/json';
    }

    await route.fulfill({
      status: 200,
      body: `Mock content for ${filename}`,
      headers: {
        'Content-Type': contentType,
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    });
  });

  const exportVariants = [
    {
      format: 'formal',
      trigger: async () => {
        // UI command stays `/export minutes`; mock normalizes it to the formal export.
        await page
          .locator('button.secretary-command[data-command="/export minutes"]').first()
          .click();
      },
    },
    {
      format: 'casual',
      trigger: async () => {
        await page
          .locator('button.secretary-command[data-command="/export casual"]').first()
          .click();
      },
    },
    {
      format: 'transcript',
      trigger: async () => {
        await page
          .locator('button.secretary-command[data-command="/export transcript"]').first()
          .click();
      },
    },
    {
      format: 'actions',
      trigger: async () => {
        await page
          .locator('button.secretary-command[data-command="/export actions"]').first()
          .click();
      },
    },
    {
      format: 'summary',
      trigger: async () => {
        await page
          .locator('button.secretary-command[data-command="/export summary"]').first()
          .click();
      },
    },
    {
      format: 'all',
      trigger: async () => {
        await page
          .locator('button.secretary-command[data-command="/export all"]').first()
          .click();
      },
    },
  ] as const;

  const testedDownloads = new Map<string, string>();

  for (const variant of exportVariants) {
    await variant.trigger();

    const exportModal = page.locator('#exportModal');
    await expect(exportModal).toBeVisible();

    const results = page.locator('#export-results [data-export-format]');
    const expectedCount = variant.format === 'all' ? 6 : 1;
    await expect(results).toHaveCount(expectedCount);

    if (variant.format === 'all') {
      const expectedFormats = ['formal', 'casual', 'transcript', 'actions', 'summary', 'data'];
      for (const expectedFormat of expectedFormats) {
        await expect(
          page.locator(`#export-results [data-export-format="${expectedFormat}"]`)
        ).toBeVisible();
      }

      const hrefs = await page.locator('#export-results .download-export').evaluateAll((elements) =>
        elements
          .map((element) => element.getAttribute('href'))
          .filter((href): href is string => typeof href === 'string')
      );

      for (const href of hrefs) {
        const absoluteUrl = new URL(href, page.url()).toString();
        const response = await page.request.get(absoluteUrl);
        expect(response.status()).toBe(200);
        const headers = response.headers();
        const filename = decodeURIComponent(href.split('/').pop() || '');
        expect(headers['content-disposition']).toContain(filename);

        const expectedContentType = href.endsWith('.md')
          ? 'text/markdown'
          : href.endsWith('.txt')
          ? 'text/plain'
          : href.endsWith('.json')
          ? 'application/json'
          : 'application/octet-stream';
        expect(headers['content-type']).toContain(expectedContentType);
      }
    } else {
      const entry = page
        .locator(`#export-results [data-export-format="${variant.format}"]`)
        .first();
      await expect(entry).toBeVisible();

      const href = await entry.locator('a.download-export').getAttribute('href');
      expect(href).not.toBeNull();

      const absoluteUrl = new URL(href!, page.url()).toString();
      const response = await page.request.get(absoluteUrl);
      expect(response.status()).toBe(200);
      const headers = response.headers();
      const filename = decodeURIComponent(href!.split('/').pop() || '');
      expect(headers['content-disposition']).toContain(filename);

      const expectedContentType = href!.endsWith('.md')
        ? 'text/markdown'
        : href!.endsWith('.txt')
        ? 'text/plain'
        : href!.endsWith('.json')
        ? 'application/json'
        : 'application/octet-stream';
      expect(headers['content-type']).toContain(expectedContentType);

      testedDownloads.set(variant.format, href!);
    }

    const closeButton = page.locator('#exportModal button[data-bs-dismiss]').first();
    if (await closeButton.isVisible()) {
      await closeButton.click();
    }

    await page.evaluate(() => {
      const modalElement = document.getElementById('exportModal');
      if (!modalElement) {
        return;
      }

      const bootstrapGlobal = (window as unknown as { bootstrap?: { Modal?: { getOrCreateInstance: (element: Element) => { hide: () => void } } } }).bootstrap;
      if (bootstrapGlobal?.Modal) {
        const instance = bootstrapGlobal.Modal.getOrCreateInstance(modalElement);
        instance.hide();
      }

      modalElement.classList.remove('show');
      modalElement.setAttribute('aria-hidden', 'true');
      (modalElement as HTMLElement).style.display = 'none';

      const backdrop = document.querySelector('.modal-backdrop');
      backdrop?.parentNode?.removeChild(backdrop);
    });

    await expect(exportModal).not.toBeVisible();
  }

  expect(testedDownloads.size).toBe(5);
});

test('should reflect secretary mode toggles in the sidebar', async ({ page }) => {
  await startConversation(page, 'Secretary mode toggles');

  const secretaryContent = page.locator('#secretary-content');

  await page.locator('button.secretary-command[data-command="/formal"]').first().click();
  await expect(secretaryContent).toContainText('Mode: formal');

  await page.locator('button.secretary-command[data-command="/casual"]').first().click();
  await expect(secretaryContent).toContainText('Mode: casual');
});
