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

let currentAgents: MockAgent[] = [...mockAgents];

test.beforeEach(async ({ page }) => {
  currentAgents = [...mockAgents];

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
                switch (trimmedMessage) {
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
                        ].join('\n'),
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
      __PLAYWRIGHT_TEST?: string;
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
