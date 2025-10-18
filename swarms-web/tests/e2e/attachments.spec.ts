import { expect, test } from './fixtures.js';
import { randomUUID } from 'crypto';
import { promises as fs } from 'fs';

const toBuffer = async (stream: NodeJS.ReadableStream | null) => {
  if (!stream) {
    return Buffer.alloc(0);
  }

  const chunks: Buffer[] = [];
  for await (const chunk of stream) {
    chunks.push(typeof chunk === 'string' ? Buffer.from(chunk) : chunk);
  }
  return Buffer.concat(chunks);
};

test.describe('Chat attachments', () => {
  test('uploads a file and handles download metadata', async ({ page, startConversation }, testInfo) => {
    await startConversation('File attachment handshake');

    const runId = `E-${randomUUID()}`;
    await page.evaluate((value) => {
      (window as unknown as { __PLAYWRIGHT_UPLOAD_RUN__?: string }).__PLAYWRIGHT_UPLOAD_RUN__ = value;
    }, runId);

    const fileName = `test-attach-${runId}.txt`;
    const fileContent = `Attachment payload for ${runId}`;
    const tempPath = testInfo.outputPath(fileName);
    await fs.writeFile(tempPath, fileContent, 'utf-8');

    const downloadPath = `/api/test-download/${runId}/${fileName}`;
    const downloadPayload = Buffer.from(`Secretary export for ${runId}`);
  let uploadRequestBody: string | null = null;
    let downloadResponseHeaders: Record<string, string> | undefined;

    await page.route(`**/api/uploads?run=${runId}`, async (route) => {
      const request = route.request();
      const headers = request.headers();
      expect(headers['content-type']).toContain('multipart/form-data');
      const body = request.postData();
      if (!body) {
        throw new Error('Upload request did not include multipart payload');
      }

      uploadRequestBody = body;
      expect(body).toContain(fileName);
      expect(body).toMatch(/Content-Disposition: form-data; name="file"; filename=".+"/);

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          download_url: downloadPath,
          file: {
            filename: fileName,
            mime: 'text/plain',
            size_bytes: fileContent.length,
            kind: 'document',
            download_url: downloadPath,
          },
        }),
      });
    });

    await page.route('**/api/test-download/**', async (route) => {
      if (!route.request().url().includes(downloadPath)) {
        await route.fallback();
        return;
      }

      expect(route.request().method()).toBe('GET');
      downloadResponseHeaders = {
        'content-type': 'application/octet-stream',
        'content-length': String(downloadPayload.length),
      };
      await route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'application/octet-stream',
          'Content-Length': String(downloadPayload.length),
          'Content-Disposition': `attachment; filename="${fileName}"`,
        },
        body: downloadPayload,
      });
    });

    const downloadPromise = page.waitForEvent('download');
    await page.locator('#file-input').setInputFiles(tempPath);

    await expect(page.locator('#toast-container')).toContainText('Upload complete');
    await expect(page.locator('#toast-container')).toContainText('Download ready');

    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(fileName);

    expect(download.url()).toContain('blob:');
    expect(downloadResponseHeaders?.['content-type']).toBe('application/octet-stream');
    expect(downloadResponseHeaders?.['content-length']).toBe(String(downloadPayload.length));

    const savedPath = testInfo.outputPath(`downloaded-${fileName}`);
    await download.saveAs(savedPath);
    const savedContent = await fs.readFile(savedPath, 'utf-8');
    expect(savedContent).toBe(downloadPayload.toString());

    const stream = await download.createReadStream();
    const buffered = await toBuffer(stream);
    expect(buffered.equals(downloadPayload)).toBeTruthy();

    expect(await download.failure()).toBeNull();
    if (!uploadRequestBody) {
      throw new Error('Upload request body missing');
    }

    const body = uploadRequestBody as string;
    expect(body).toMatch(/\r\n--/);
  });
});
