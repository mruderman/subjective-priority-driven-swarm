import { expect, Page } from '@playwright/test';

import { cloneAgents, mockData, MockAgent } from './mockData.js';

const STORAGE_KEY = '__PW_MOCK_LETTA_STATE__';

const cloneState = (agents: MockAgent[], secretaryMinutes: string, agentResponse: string) => ({
  agents: cloneAgents(agents),
  secretaryMinutes,
  agentResponse,
});

export class MockedLettaController {
  private currentAgents: MockAgent[];
  private secretaryMinutes: string;
  private agentResponse: string;
  private routesRegistered = false;

  constructor(private readonly page: Page) {
    this.currentAgents = cloneAgents(mockData.agents);
    this.secretaryMinutes = mockData.secretaryMinutes;
    this.agentResponse = mockData.agentResponse;
  }

  async init(): Promise<void> {
    // Add test-only page hook early to make it available to app scripts
    await this.page.addInitScript(() => {
      // Test-only global hook to emit Socket.IO events when available
      // It will attempt to emit immediately and retry once if the socket isn't ready yet.
      window['__TEST_EMIT'] = (eventName, data) => {
        try {
          const tryEmit = () => {
            const socket =
              (window['simpleChat'] && window['simpleChat'].socket) ||
              (window['swarmsApp'] && window['swarmsApp'].socket);
            if (socket && typeof socket.emit === 'function') {
              socket.emit(String(eventName), data);
              return true;
            }
            return false;
          };
          if (!tryEmit()) {
            // Retry after a short delay if socket not ready
            setTimeout(tryEmit, 50);
          }
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error('TEST_EMIT error', e);
        }
      };
    });

    await this.syncStateWithPage();
    await this.registerTestFlag();
    await this.registerSocketStub();
    await this.registerRoutes();
  }

  async reset(): Promise<void> {
    this.currentAgents = cloneAgents(mockData.agents);
    this.secretaryMinutes = mockData.secretaryMinutes;
    this.agentResponse = mockData.agentResponse;
    await this.syncStateWithPage();
  }

  async setAgents(agents: MockAgent[]): Promise<void> {
    this.currentAgents = cloneAgents(agents);
    await this.syncStateWithPage();
  }

  async setSecretaryMinutes(minutes: string): Promise<void> {
    this.secretaryMinutes = minutes;
    await this.syncStateWithPage();
  }

  async setAgentResponse(response: string): Promise<void> {
    this.agentResponse = response;
    await this.syncStateWithPage();
  }

  getAgents(): MockAgent[] {
    return cloneAgents(this.currentAgents);
  }

  async startConversation(topic = 'Exploring AI collaboration'): Promise<void> {
    await this.page.goto('/setup');

    const agentCards = this.page.locator('.agent-card');
    await expect(agentCards.first()).toBeVisible();

    await agentCards.nth(0).locator('input.agent-checkbox').check();
    await agentCards.nth(1).locator('input.agent-checkbox').check();

    await this.page.locator('.mode-card').first().click();
    await this.page.locator('#topic').fill(topic);

    await this.page.locator('#start-chat-btn').click();

    await this.page.waitForResponse('**/api/start_session');
    await expect(this.page.locator('#chat-input')).toBeVisible();
  }

  async dispose(): Promise<void> {
    if (this.routesRegistered) {
      await this.page.unroute('**/socket.io.min.js*');
      await this.page.unroute('**/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js*');
      await this.page.unroute('**/api/agents');
      this.routesRegistered = false;
    }
  }

  private async syncStateWithPage(): Promise<void> {
    const state = cloneState(this.currentAgents, this.secretaryMinutes, this.agentResponse);

    await this.page.addInitScript(
      ({ storageKey, value }) => {
        try {
          sessionStorage.setItem(storageKey, JSON.stringify(value));
        } catch (error) {
          console.warn('Failed to persist Playwright mock state', error);
        }
      },
      { storageKey: STORAGE_KEY, value: state }
    );

    if (this.page.url() !== 'about:blank') {
      await this.page.evaluate(
        ({ storageKey, value }) => {
          sessionStorage.setItem(storageKey, JSON.stringify(value));
          const win = window as typeof window & { __PLAYWRIGHT_RESET_SOCKET?: () => void };
          if (typeof win.__PLAYWRIGHT_RESET_SOCKET === 'function') {
            win.__PLAYWRIGHT_RESET_SOCKET();
          }
        },
        { storageKey: STORAGE_KEY, value: state }
      );
    }
  }

  private async registerTestFlag(): Promise<void> {
    await this.page.addInitScript(() => {
      (window as unknown as { __PLAYWRIGHT_TEST?: string }).__PLAYWRIGHT_TEST = '1';
      try {
        sessionStorage.setItem('sessionId', 'session-test');
      } catch (error) {
        // Ignore storage errors (e.g., disabled cookies)
      }
    });
  }

  private async registerSocketStub(): Promise<void> {
    await this.page.addInitScript(
      ({ storageKey }) => {
        const getState = () => {
          const defaults = {
            agents: [],
            secretaryMinutes: 'Meeting Minutes\n- Agenda review\n- Decisions recorded',
            agentResponse: 'AI advancements look promising with collaborative intelligence.',
          } as const;

          try {
            const raw = sessionStorage.getItem(storageKey);
            if (!raw) {
              return { ...defaults };
            }
            const parsed = JSON.parse(raw);
            const agents = Array.isArray(parsed.agents) ? parsed.agents : [];
            return {
              agents,
              secretaryMinutes:
                typeof parsed.secretaryMinutes === 'string'
                  ? parsed.secretaryMinutes
                  : defaults.secretaryMinutes,
              agentResponse:
                typeof parsed.agentResponse === 'string'
                  ? parsed.agentResponse
                  : defaults.agentResponse,
            };
          } catch (error) {
            console.error('Failed to parse Playwright mock state', error);
            return { ...defaults };
          }
        };

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
          const win = window as typeof window & { bootstrap?: { Toast: typeof BootstrapToastStub } };
          if (!win.bootstrap) {
            win.bootstrap = { Toast: BootstrapToastStub };
          }
        };

        type Listener = (payload?: unknown) => void;
        type SocketStub = {
          on: (event: string, callback: Listener) => SocketStub;
          off: (event?: string) => SocketStub;
          emit: (event: string, payload?: Record<string, unknown>) => SocketStub;
          disconnect: () => void;
          __playwrightEmitDirect?: (event: string, payload?: unknown) => void;
        };

        let socketInstance: SocketStub | null = null;

        const createSocketFactory = () => {
          if (socketInstance) {
            return socketInstance;
          }

          const listeners = new Map<string, Listener[]>();
          const commandTimers = new Map<string, number[]>();

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

          const clearCommandTimers = (commandKey?: string) => {
            const keys = typeof commandKey === 'string' ? [commandKey] : Array.from(commandTimers.keys());
            keys.forEach((key) => {
              const timers = commandTimers.get(key);
              if (timers) {
                timers.forEach((timerId) => {
                  try {
                    clearTimeout(timerId);
                  } catch (error) {
                    console.warn('Failed to clear mock command timer', error);
                  }
                });
                commandTimers.delete(key);
              }
            });
          };

          const scheduleCommandTasks = (
            commandKey: string,
            tasks: { delay: number; run: () => void }[]
          ) => {
            clearCommandTimers(commandKey);

            if (!Array.isArray(tasks) || tasks.length === 0) {
              return;
            }

            const activeTimers: number[] = [];

            tasks.forEach((task) => {
              const delay = typeof task.delay === 'number' ? task.delay : 0;
              const timerId = window.setTimeout(() => {
                try {
                  task.run();
                } finally {
                  const timers = commandTimers.get(commandKey);
                  if (timers) {
                    const index = timers.indexOf(timerId);
                    if (index >= 0) {
                      timers.splice(index, 1);
                    }
                    if (timers.length === 0) {
                      commandTimers.delete(commandKey);
                    } else {
                      commandTimers.set(commandKey, timers);
                    }
                  }
                }
              }, delay);

              activeTimers.push(timerId);
            });

            if (activeTimers.length > 0) {
              commandTimers.set(commandKey, activeTimers);
            }
          };

          const socket: SocketStub = {
            on(event: string, callback: Listener) {
              ensureListeners(event).push(callback);
              if (event === 'connect') {
                setTimeout(() => callback(undefined), 0);
              }
              return socket;
            },
            off(event?: string) {
              if (typeof event === 'string') {
                listeners.delete(event);
              } else {
                listeners.clear();
              }
              return socket;
            },
            emit(event: string, payload?: Record<string, unknown>) {
              const state = getState();

              if (event === 'join_session' && payload?.session_id) {
                setTimeout(() => emitEvent('joined', { session_id: payload.session_id }), 0);
              }

              if (event === 'start_chat' && payload?.topic) {
                setTimeout(() => {
                  emitEvent('chat_started', {
                    topic: payload.topic,
                    mode: 'hybrid',
                    agents: state.agents.map((agent: { id: string; name: string }) => ({
                      name: agent.name,
                      id: agent.id,
                    })),
                    secretary_enabled: true,
                  });
                }, 50);
              }

              if (event === 'user_message' && typeof payload?.message === 'string') {
                const message = String(payload.message);
                const timestamp = new Date().toISOString();

                setTimeout(() => {
                  emitEvent('user_message', {
                    speaker: 'You',
                    message,
                    timestamp,
                  });
                }, 0);

                const trimmed = message.trim();

                if (trimmed.startsWith('/')) {
                  const [rawCommand] = trimmed.split(/\s+/, 1);
                  const commandKey = rawCommand.slice(1).toLowerCase();
                  const schedule = (
                    key: string,
                    tasks: { delay: number; run: () => void }[]
                  ) => scheduleCommandTasks(key, tasks);

                  if (commandKey === 'minutes') {
                    schedule(commandKey, [
                      {
                        delay: 60,
                        run: () => {
                          emitEvent('secretary_activity', {
                            activity: 'generating',
                            message: '📝 Generating meeting minutes...',
                          });
                        },
                      },
                      {
                        delay: 140,
                        run: () => {
                          const minutesContainer = document.getElementById('secretary-minutes');
                          if (minutesContainer) {
                            minutesContainer.style.display = 'block';
                          }
                          emitEvent('secretary_minutes', {
                            minutes: state.secretaryMinutes,
                          });
                        },
                      },
                      {
                        delay: 220,
                        run: () => {
                          emitEvent('secretary_activity', {
                            activity: 'completed',
                            message: '✅ Meeting minutes generated!',
                          });
                        },
                      },
                    ]);
                  } else if (commandKey === 'stats') {
                    schedule(commandKey, [
                      {
                        delay: 70,
                        run: () => {
                          emitEvent('secretary_activity', {
                            activity: 'generating',
                            message: '📊 Gathering conversation statistics...',
                          });
                        },
                      },
                      {
                        delay: 160,
                        run: () => {
                          const activeAgents = Array.isArray(state.agents)
                            ? state.agents.length
                            : 0;
                          const respondingAgents = Math.min(activeAgents, 2);
                          emitEvent('secretary_stats', {
                            stats: {
                              'Total Messages': 12,
                              'Agents Responded': `${respondingAgents} / ${activeAgents || respondingAgents}`,
                              'Action Items Logged': 3,
                            },
                          });
                        },
                      },
                      {
                        delay: 240,
                        run: () => {
                          emitEvent('secretary_activity', {
                            activity: 'completed',
                            message: '📈 Conversation stats are ready!',
                          });
                        },
                      },
                    ]);
                  } else if (commandKey === 'memory-status') {
                    schedule(commandKey, [
                      {
                        delay: 90,
                        run: () => {
                          const agentCount = Array.isArray(state.agents)
                            ? state.agents.length
                            : 0;
                          emitEvent('secretary_status', {
                            status: 'awareness',
                            agent_name: 'Memory Monitor',
                            mode: 'memory tracking',
                            message: `Memory status summarized for ${agentCount || 0} agents.`,
                          });
                        },
                      },
                    ]);
                  } else if (commandKey === 'memory-awareness') {
                    schedule(commandKey, [
                      {
                        delay: 90,
                        run: () => {
                          emitEvent('secretary_status', {
                            status: 'insight',
                            agent_name: 'Memory Monitor',
                            mode: 'awareness check',
                            message: 'Agents notified about recent memory usage.',
                          });
                        },
                      },
                    ]);
                  } else if (commandKey === 'help' || commandKey === 'commands') {
                    schedule(commandKey, [
                      {
                        delay: 80,
                        run: () => {
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
                              'Documentation: https://docs.letta.ai/commands',
                              '  /help              - Show this help message',
                            ].join('\n'),
                            timestamp: new Date().toISOString(),
                          });
                        },
                      },
                    ]);
                  } else {
                    schedule('unknown', [
                      {
                        delay: 60,
                        run: () => {
                          emitEvent('secretary_status', {
                            status: 'error',
                            agent_name: 'Secretary',
                            mode: 'command-center',
                            message: 'Unknown command',
                          });
                        },
                      },
                    ]);
                  }
                } else {
                  setTimeout(() => {
                    const fallbackSpeaker =
                      state.agents[0]?.name || 'Agent';
                    const fallbackMessage =
                      state.agentResponse ||
                      'AI advancements look promising with collaborative intelligence.';
                    emitEvent('agent_message', {
                      speaker: fallbackSpeaker,
                      message: fallbackMessage,
                      timestamp: new Date().toISOString(),
                      phase: 'response',
                    });
                  }, 150);
                }
              }

              return socket;
            },
            disconnect() {
              clearCommandTimers();
              listeners.clear();
              socketInstance = null;
            },
          };

          socket.__playwrightEmitDirect = emitEvent;

          socketInstance = socket;
          return socketInstance;
        };

        ensureBootstrap();

        const win = window as typeof window & {
          __playwrightCreateSocketIO?: () => SocketStub;
          io?: () => unknown;
          __PLAYWRIGHT_RESET_SOCKET?: () => void;
          __playwrightEmitSocketEvent?: (event: string, payload?: unknown) => void;
        };

        win.__playwrightCreateSocketIO = () => createSocketFactory();
        win.io = () => createSocketFactory();
        win.__PLAYWRIGHT_RESET_SOCKET = () => {
          if (socketInstance && typeof socketInstance.disconnect === 'function') {
            try {
              socketInstance.disconnect();
            } catch (error) {
              console.warn('Failed to disconnect mock socket instance', error);
            }
          } else {
            clearCommandTimers();
          }
          socketInstance = null;
        };
        win.__playwrightEmitSocketEvent = (event: string, payload?: unknown) => {
          const socket = createSocketFactory();
          const emitter = socket.__playwrightEmitDirect;
          if (typeof emitter === 'function') {
            emitter(event, payload);
          }
        };
      },
      { storageKey: STORAGE_KEY }
    );
  }

  private async registerRoutes(): Promise<void> {
    await this.page.route('**/socket.io.min.js*', async (route) => {
      await route.fulfill({
        contentType: 'application/javascript',
        body: 'window.io = window.io || (window.__playwrightCreateSocketIO && window.__playwrightCreateSocketIO());',
      });
    });

    await this.page.route('**/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js*', async (route) => {
      await route.fulfill({
        contentType: 'application/javascript',
        body: 'window.bootstrap = window.bootstrap || { Toast: function ToastStub(){ this.show = function(){}; } };',
      });
    });

    await this.page.route('**/api/agents', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ agents: this.currentAgents }),
      });
    });

    this.routesRegistered = true;
  }
}
