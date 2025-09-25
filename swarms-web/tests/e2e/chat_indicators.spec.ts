import { expect, test } from './fixtures.js';

test.describe('Chat indicator coverage', () => {
  test('shows thinking indicators until an agent responds', async ({ startConversation, emitSocketEvent, page }) => {
    const topic = 'Thinking indicator coverage';
    await startConversation(topic);

    await emitSocketEvent('agent_thinking', {
      agent: 'Alex Johnson',
      phase: 'analysis',
      progress: '2/3',
    });

    const indicator = page.locator('.thinking-indicator');
    await expect(indicator).toBeVisible();
    await expect(indicator).toContainText('Alex Johnson is thinking');
    await expect(indicator).toContainText('analysis');
    await expect(indicator).toContainText('2/3');

    await emitSocketEvent('agent_message', {
      speaker: 'Alex Johnson',
      message: 'Here is an analysis insight from Alex.',
      timestamp: new Date().toISOString(),
      phase: 'analysis',
    });

    await expect(indicator).not.toBeVisible();
    await expect(page.locator('#chat-messages .message.agent').last()).toContainText('analysis insight');
  });

  test('renders assessment progress and motivation scores', async ({ startConversation, emitSocketEvent, page }) => {
    await startConversation('Scoreboard coverage');

    await emitSocketEvent('assessing_agents', {});
    const progressIndicator = page.locator('#assessment-indicator');
    await expect(progressIndicator).toBeVisible();
    await expect(progressIndicator).toContainText('Assessing agent motivations');

    await emitSocketEvent('agent_scores', {
      scores: [
        { name: 'Alex Johnson', motivation_score: '0.82', priority_score: '0.67' },
        { name: 'Jordan Smith', motivation_score: '0.74', priority_score: '0.72' },
      ],
    });

    const scoresWrapper = page.locator('#agent-scores-container');
    await expect(progressIndicator).not.toBeVisible();
    await expect(scoresWrapper).toBeVisible();
    await expect(scoresWrapper).not.toHaveAttribute('hidden');
    await expect(scoresWrapper).toContainText('Alex Johnson');
    await expect(scoresWrapper).toContainText('M: 0.82');
    await expect(scoresWrapper).toContainText('P: 0.67');
    await expect(scoresWrapper).toContainText('Jordan Smith');

    await emitSocketEvent('agent_scores', { scores: [] });
    await expect(scoresWrapper).toBeHidden();
    await expect(scoresWrapper).toHaveAttribute('hidden', 'true');
  });

  test('updates the phase indicator and toast styling', async ({ startConversation, emitSocketEvent, page }) => {
    const topic = 'Phase coverage topic';

    await startConversation(topic);

    await emitSocketEvent('chat_started', {
      topic,
      mode: 'hybrid',
      agents: [
        { id: 'agent-1', name: 'Alex Johnson' },
        { id: 'agent-2', name: 'Jordan Smith' },
      ],
      secretary_enabled: true,
    });

    const chatToast = page
      .locator('#toast-container .toast')
      .filter({ hasText: `Chat started: ${topic}` })
      .first();
    await expect(chatToast).toBeVisible({ timeout: 10000 });
    await expect(chatToast).toHaveClass(/bg-success/);

    await emitSocketEvent('phase_change', { phase: 'response_round' });
    await expect(page.locator('#phase-indicator')).toHaveText(/Response Round/);

    await page.evaluate(() => {
      const win = window as unknown as {
        swarmsApp: { showToast: (message: string, type?: string) => void };
      };
      win.swarmsApp.showToast('Heads up warning', 'warning');
      win.swarmsApp.showToast('All clear success', 'success');
    });

    const warningToast = page
      .locator('#toast-container .toast')
      .filter({ hasText: 'Heads up warning' })
      .first();
    const successToast = page
      .locator('#toast-container .toast')
      .filter({ hasText: 'All clear success' })
      .first();

    await expect(warningToast).toBeVisible();
    await expect(warningToast).toHaveClass(/bg-warning/);
    await expect(successToast).toBeVisible();
    await expect(successToast).toHaveClass(/bg-success/);
  });
});
