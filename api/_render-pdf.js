// api/_render-pdf.js
import chromium from 'chrome-aws-lambda';
import puppeteer from 'puppeteer-core';

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const token = req.headers['x-render-token'];
  if (token !== process.env.RENDER_TOKEN) return res.status(401).json({ error: 'Unauthorized' });

  const { html } = req.body || {};
  if (!html) return res.status(400).json({ error: 'Missing html' });

  let browser = null;
  try {
    const execPath = await chromium.executablePath;
    browser = await puppeteer.launch({
      args: chromium.args,
      defaultViewport: chromium.defaultViewport,
      executablePath: execPath || '/usr/bin/chromium-browser',
      headless: chromium.headless,
    });

    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: 'networkidle0' });
    await page.evaluate('document.fonts.ready');
    const pdf = await page.pdf({ format: 'A4', printBackground: true, margin: { top: '12mm', bottom: '14mm', left: '10mm', right: '10mm' } });

    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Length', pdf.length);
    res.status(200).send(pdf);
  } catch (err) {
    console.error('Render error', err);
    res.status(500).json({ error: 'Render failed', details: String(err) });
  } finally {
    if (browser) await browser?.close();
  }
}
