import { expect, test } from './fixtures.js';

const THINKING_AGENT = 'Alex Johnson';

function uniqueTopic(): string {
  return `Prompt B conversation flow ${Date.now()}`;
}

test.describe('Prompt B conversation flow', () => {
  test('renders ordered chat bubbles and clears interim indicators', async ({
    startConversation,
    emitSocketEvent,
    page,
    setAgentResponse,
  }) => {
    const userMessage = 'How is the swarm prioritizing current objectives?';
    const agentReply = 'Priorities are rotated based on momentum and urgency in this mock reply.';

    await setAgentResponse(agentReply);
    await startConversation(uniqueTopic());

    const chatInput = page.locator('#chat-input');
    await chatInput.fill(userMessage);
    await chatInput.press('Enter');

    const firstUserBubble = page
      .locator('#chat-messages .message.user')
      .filter({ hasText: userMessage })
      .first();
    await expect(firstUserBubble).toBeVisible();

    await chatInput.fill(userMessage);
    await chatInput.press('Enter');

    await emitSocketEvent('agent_thinking', {
      agent: THINKING_AGENT,
      phase: 'response',
      progress: '1/1',
    });

    const latestUserBubble = page
      .locator('#chat-messages .message.user')
      .filter({ hasText: userMessage })
      .last();
    await expect(latestUserBubble).toBeVisible();

    const thinkingIndicator = page
      .locator('.thinking-indicator')
      .filter({ hasText: THINKING_AGENT })
      .first();
    await expect(thinkingIndicator).toBeVisible();

    const agentBubble = page
      .locator('#chat-messages .message.agent')
      .filter({ hasText: agentReply })
      .first();
    await expect(agentBubble).toBeVisible();

    await expect(thinkingIndicator).toBeHidden();

    const ordering = await page.evaluate(
      ({ userText, agentText }) => {
        const nodes = Array.from(
          document.querySelectorAll('#chat-messages .message')
        );
        const userIndex = nodes.findIndex(
          (node) =>
            node.classList.contains('user') &&
            node.textContent?.includes(userText)
        );
        const agentIndex = nodes.findIndex(
          (node) =>
            node.classList.contains('agent') &&
            node.textContent?.includes(agentText)
        );
        return { userIndex, agentIndex };
      },
      { userText: userMessage, agentText: agentReply }
    );

    expect(ordering.userIndex).toBeGreaterThan(-1);
    expect(ordering.agentIndex).toBeGreaterThan(-1);
    expect(ordering.userIndex).toBeLessThan(ordering.agentIndex);

    await expect(page.locator('#secretary-minutes')).toBeHidden();
    await expect(page.locator('#exportModal')).toHaveAttribute('aria-hidden', 'true');
  });
});
