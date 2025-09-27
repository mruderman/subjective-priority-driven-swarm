import { expect, Page } from '@playwright/test';

import { test } from './fixtures.js';

const getCharacterLimit = async (page: Page) => {
  return page.evaluate(() => {
    const globalLimit = (window as typeof window & { __CHAT_MESSAGE_LIMIT__?: number }).__CHAT_MESSAGE_LIMIT__;
    if (typeof globalLimit === 'number' && Number.isFinite(globalLimit)) {
      return globalLimit;
    }
    const simpleChat = (window as typeof window & { simpleChat?: { messageLimit?: number } }).simpleChat;
    if (simpleChat && typeof simpleChat.messageLimit === 'number') {
      return simpleChat.messageLimit;
    }
    return 24000;
  });
};

const startConversationFromSetup = async (page: Page, topic: string) => {
  await page.goto('/setup');

  const agentCards = page.locator('.agent-card');
  await expect(agentCards.first()).toBeVisible();
  await agentCards.nth(0).locator('input.agent-checkbox').check();
  await agentCards.nth(1).locator('input.agent-checkbox').check();

  await page.locator('.mode-card').first().click();
  await page.locator('#topic').fill(topic);

  await Promise.all([
    page.waitForResponse('**/api/start_session'),
    page.locator('#start-chat-btn').click(),
  ]);

  await expect(page.locator('#chat-input')).toBeVisible();
};

test.describe('Token limit safeguards', () => {
  test('warns and trims when the message exceeds the configured limit', async ({ page, mockedLetta }) => {
    await mockedLetta.reset();
    await startConversationFromSetup(page, 'Token limit regression check');

    const limit = await getCharacterLimit(page);
    const overflowAmount = 512;
    const longMessage = 'A'.repeat(limit + overflowAmount) + ' -- trimmed check';

    await page.fill('#chat-input', longMessage);
    await page.click('#send-button');

    const banner = page.locator('#token-limit-banner');
    await expect(banner).toBeVisible();
    await expect(banner).toContainText('Message trimmed');
    await expect(page.locator('#show-trimmed-full')).toBeEnabled();

    const messageContent = page.locator('.message.user .message-content').last();
    await expect(messageContent).toContainText(longMessage.slice(0, 100));

    const trimmedText = await messageContent.evaluate((element) => element.textContent ?? '');
    expect(trimmedText.length).toBe(limit);
    expect(trimmedText).toBe(longMessage.slice(0, limit));

    await page.click('#show-trimmed-full');

    const modal = page.locator('#trimmedMessageModal');
    await expect(modal).toBeVisible();

    const fullMessage = await modal.locator('#trimmed-message-full').evaluate((element) => element.textContent ?? '');
    expect(fullMessage.length).toBe(longMessage.length);
    expect(fullMessage.slice(0, 120)).toBe(longMessage.slice(0, 120));
    expect(fullMessage.slice(-120)).toBe(longMessage.slice(-120));

    const sentCount = await modal.locator('#trimmed-message-count').innerText();
    const numericSentCount = Number(sentCount.replace(/[^0-9]/g, ''));
    expect(numericSentCount).toBe(limit);

    await page.evaluate(() => {
      const modalElement = document.getElementById('trimmedMessageModal');
      if (!modalElement) {
        return;
      }
      const bootstrap = (window as typeof window & { bootstrap?: { Modal?: { getOrCreateInstance?: (element: Element) => { hide: () => void } } } }).bootstrap;
      bootstrap?.Modal?.getOrCreateInstance?.(modalElement)?.hide();
      modalElement.classList.remove('show');
      modalElement.style.display = 'none';
      modalElement.setAttribute('aria-hidden', 'true');
    });

    const secondMessage = 'B'.repeat(limit + Math.floor(overflowAmount / 2)) + ' -- follow up';
    await page.fill('#chat-input', secondMessage);
    await page.click('#send-button');

    await page.waitForFunction(() => {
      const nodes = document.querySelectorAll('.message.user .message-content');
      return nodes.length >= 2;
    });

    await page.click('#show-trimmed-full');

    await expect(modal).toBeVisible();

    const secondFullMessage = await modal.locator('#trimmed-message-full').evaluate((element) => element.textContent ?? '');
    expect(secondFullMessage.length).toBe(secondMessage.length);
    expect(secondFullMessage.slice(0, 120)).toBe(secondMessage.slice(0, 120));
    expect(secondFullMessage.slice(-120)).toBe(secondMessage.slice(-120));

    await page.evaluate(() => {
      const modalElement = document.getElementById('trimmedMessageModal');
      if (!modalElement) {
        return;
      }
      const bootstrap = (window as typeof window & { bootstrap?: { Modal?: { getOrCreateInstance?: (element: Element) => { hide: () => void } } } }).bootstrap;
      bootstrap?.Modal?.getOrCreateInstance?.(modalElement)?.hide();
      modalElement.classList.remove('show');
      modalElement.style.display = 'none';
      modalElement.setAttribute('aria-hidden', 'true');
    });

    const latestContent = await page.locator('.message.user .message-content').last().evaluate((element) => element.textContent ?? '');
    expect(latestContent.length).toBe(limit);
    expect(latestContent).toBe(secondMessage.slice(0, limit));
  });

  test('allows messages exactly at the limit without trimming or warnings', async ({ page, mockedLetta }) => {
    await mockedLetta.reset();
    await startConversationFromSetup(page, 'Token limit boundary');

    const limit = await getCharacterLimit(page);
    const exactMessage = 'C'.repeat(limit);

    await page.fill('#chat-input', exactMessage);
    await page.click('#send-button');

    const banner = page.locator('#token-limit-banner');
    await expect(banner).toBeHidden();
    await expect(page.locator('#show-trimmed-full')).toBeDisabled();

    const messageContent = page.locator('.message.user .message-content').last();
    await expect(messageContent).toContainText(exactMessage.slice(0, 100));

    const renderedText = await messageContent.evaluate((element) => element.textContent ?? '');
    expect(renderedText.length).toBe(limit);
    expect(renderedText).toBe(exactMessage);

    const trimmedState = await page.evaluate(() => {
      const chat = (window as typeof window & { simpleChat?: { lastTrimmedMessage?: unknown } }).simpleChat;
      return chat?.lastTrimmedMessage ?? null;
    });
    expect(trimmedState).toBeNull();
  });
});
