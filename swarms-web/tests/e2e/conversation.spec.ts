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

test.beforeEach(async ({ page }) => {
  await page.addInitScript(({ agents }) => {
    const mockAgentsData = agents as MockAgent[];

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

    const ensureBootstrap = () => {
      const win = window as typeof window & {
        bootstrap?: { Toast: typeof BootstrapToastStub };
      };
      if (!win.bootstrap) {
        win.bootstrap = { Toast: BootstrapToastStub };
      }
    };

    const createSocketFactory = () => {
      let socket: {
        on: (event: string, callback: (payload?: unknown) => void) => typeof socket;
        off: (event?: string) => typeof socket;
        emit: (event: string, payload?: Record<string, unknown>) => typeof socket;
        disconnect: () => void;
      } | null = null;

      const factory = () => {
        if (socket) {
          return socket;
        }

        const listeners = new Map<string, ((payload?: unknown) => void)[]>();

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

        const socketInstance = {
          on(event: string, callback: (payload?: unknown) => void) {
            ensureListeners(event).push(callback);
            if (event === 'connect') {
              setTimeout(() => callback(undefined), 0);
            }
            return socketInstance;
          },
          off(event?: string) {
            if (!event) {
              listeners.clear();
            } else {
              listeners.delete(event);
            }
            return socketInstance;
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
                  agents: mockAgentsData.map((agent) => ({ name: agent.name, id: agent.id })),
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
                if (trimmedMessage === '/minutes') {
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

            return socketInstance;
          },
          disconnect() {
            listeners.clear();
          },
        };

        socket = socketInstance;
        return socketInstance;
      };

      return factory;
    };

    ensureBootstrap();

    const win = window as typeof window & {
      __playwrightCreateSocketIO?: () => () => unknown;
      io?: () => unknown;
    };

    win.__playwrightCreateSocketIO = createSocketFactory;
    const socketFactory = createSocketFactory();
    win.io = () => socketFactory();
  }, { agents: mockAgents });

  await page.route('**/socket.io.min.js*', async (route) => {
    await route.fulfill({
      contentType: 'application/javascript',
      body: 'window.io = window.io || (window.__playwrightCreateSocketIO && window.__playwrightCreateSocketIO());',
    });
  });

  await page.route('**/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js*', async (route) => {
    await route.fulfill({
      contentType: 'application/javascript',
      body: 'window.bootstrap = window.bootstrap || { Toast: function ToastStub(){ this.show = function(){}; } };',
    });
  });

  await page.route('**/api/agents', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ agents: mockAgents }),
    });
  });

  await page.route('**/api/start_session', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ session_id: 'session-test', status: 'success' }),
    });
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

  await Promise.all([
    page.waitForURL('**/chat'),
    page.locator('#start-chat-btn').click(),
  ]);

  await expect(page.locator('#chat-input')).toBeVisible();
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

  await page.locator('#chat-input').fill('/minutes');
  await page.locator('#send-button').click();

  const minutesContent = page.locator('#secretary-minutes');
  await expect(minutesContent).toContainText('Meeting Minutes');
});
