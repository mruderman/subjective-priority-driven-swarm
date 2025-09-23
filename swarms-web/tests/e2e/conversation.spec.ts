import { expect, test } from './fixtures.js';

test('should load the main page and display agent selection cards', async ({ page }) => {
  await page.goto('/setup');

  await expect(page.getByText('Subjective Priority-Driven Swarm')).toBeVisible();
  await expect(page.locator('.agent-card').first()).toBeVisible();
});

test(
  'should allow a user to select agents, start a chat, and see agent responses',
  async ({ page, startConversation }) => {
    await startConversation('The future of AI collaboration');

    await page.locator('#chat-input').fill('What is the future of AI?');
    await page.locator('#send-button').click();

    const userMessage = page
      .locator('#chat-messages .message.user')
      .filter({ hasText: 'What is the future of AI?' });
    await expect(userMessage).toHaveCount(1);

    const agentMessage = page.locator('#chat-messages .message.agent').first();
    await expect(agentMessage).toBeVisible();
    await expect(agentMessage.locator('.message-content')).not.toHaveText(/^\s*$/);
  }
);

test('should respond to the /minutes slash command', async ({ page, startConversation }) => {
  await startConversation('Documenting project updates');

  await page.locator('#chat-input').fill('/minutes');
  await page.locator('#send-button').click();

  const minutesContent = page.locator('#secretary-minutes');
  await expect(minutesContent).toContainText('Meeting Minutes');
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

test('should show a warning when no agents are returned from the server', async ({ page, mockedLetta }) => {
  await mockedLetta.setAgents([]);
  await page.goto('/setup');

  const noAgentsAlert = page.locator('#no-agents');
  await expect(noAgentsAlert).toBeVisible();
  await expect(page.locator('#agent-count')).toHaveText('None Available');
});
