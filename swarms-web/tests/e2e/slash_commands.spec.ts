import { expect, test } from './fixtures.js';

const sendSlashCommand = async (page: import('@playwright/test').Page, command: string) => {
  await page.locator('#chat-input').fill(command);
  await page.locator('#send-button').click();
};

test.describe('Secretary slash commands', () => {
  test('reveals meeting minutes when /minutes is submitted', async ({ startConversation, page }) => {
    await startConversation('Minutes coverage scenario');

    await sendSlashCommand(page, '/minutes');

    const minutesPanel = page.locator('#secretary-minutes pre');
    await expect(minutesPanel).toBeVisible();
    await expect(minutesPanel).toContainText('Meeting Minutes');
    await expect(page.locator('#secretary-content')).toContainText('Meeting minutes generated');
  });

  test('displays conversation statistics for /stats', async ({ startConversation, page }) => {
    await startConversation('Stats coverage scenario');

    await sendSlashCommand(page, '/stats');

    const statsPanel = page.locator('#secretary-stats');
    const statRows = statsPanel.locator('.d-flex.justify-content-between');

    await expect(statRows).toHaveCount(3);
    await expect(statRows.nth(0)).toContainText('Total Messages');
    await expect(statRows.nth(1)).toContainText('Agents Responded');
    await expect(statRows.nth(2)).toContainText('Action Items Logged');
    await expect(page.locator('#secretary-content')).toContainText('Conversation stats are ready');
  });

  test('surfaces a toast describing memory usage for /memory-status', async ({ startConversation, page }) => {
    await startConversation('Memory status scenario');

    await sendSlashCommand(page, '/memory-status');

    const toast = page.locator('#toast-container .toast').last();
    await expect(toast).toBeVisible();
    await expect(toast).toContainText('Memory status summarized for 3 agents.');
  });

  test('alerts agents about awareness checks for /memory-awareness', async ({ startConversation, page }) => {
    await startConversation('Memory awareness scenario');

    await sendSlashCommand(page, '/memory-awareness');

    const toast = page.locator('#toast-container .toast').last();
    await expect(toast).toBeVisible();
    await expect(toast).toContainText('Agents notified about recent memory usage.');
  });

  test('shows help documentation and links for /help', async ({ startConversation, page }) => {
    await startConversation('Help command scenario');

    await sendSlashCommand(page, '/help');

    const helpMessage = page
      .locator('#chat-messages .message.system')
      .filter({ hasText: 'Available Commands' })
      .first();

    await expect(helpMessage).toBeVisible();
    await expect(helpMessage).toContainText('/memory-status');
    await expect(helpMessage).toContainText('/stats');
    const docsLink = helpMessage.locator('a[href="https://docs.letta.ai/commands"]');
    await expect(docsLink).toHaveCount(1);
  });

  test('warns about unknown commands with a toast notification', async ({ startConversation, page }) => {
    await startConversation('Unknown command scenario');

    await sendSlashCommand(page, '/does-not-exist');

    const toast = page.locator('#toast-container .toast').last();
    await expect(toast).toBeVisible();
    await expect(toast).toContainText('Unknown command');
  });

  test('does not duplicate results when /stats is issued repeatedly', async ({ startConversation, page }) => {
    await startConversation('Repeated stats scenario');

    await sendSlashCommand(page, '/stats');
    await sendSlashCommand(page, '/stats');

    const statRows = page.locator('#secretary-stats .d-flex.justify-content-between');
    await expect(statRows).toHaveCount(3);
    await expect(statRows.nth(1)).toContainText('Agents Responded');
  });
});
