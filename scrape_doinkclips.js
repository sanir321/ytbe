const puppeteer = require('puppeteer-core');
const fs = require('fs');

(async () => {
  const cookieLines = fs.readFileSync('/home/samirkhadka/instagram_cookies.txt', 'utf8').split('\n');
  const cookies = [];
  for (const line of cookieLines) {
    if (line.startsWith('#') || !line.trim()) continue;
    const parts = line.split('\t');
    if (parts.length >= 7) {
      cookies.push({
        name: parts[5],
        value: parts[6].trim(),
        domain: parts[0],
        path: parts[2],
        secure: parts[3].toLowerCase() === 'true',
        httpOnly: false
      });
    }
  }

  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: 'new',
    userDataDir: '/tmp/insta_doinkclips_profile',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-blink-features=AutomationControlled',
      '--disable-dev-shm-usage',
      '--window-size=1280,1000'
    ]
  });

  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36');
  await page.setCookie(...cookies);

  const acc = 'doinkclips';
  console.log(`🚀 Scraping all reels for @${acc}...`);

  const accReels = new Set();

  const onResponse = async (res) => {
    const url = res.url();
    if (url.includes('graphql') || url.includes('/clips/') || url.includes('/api/v1/')) {
      try {
        const text = await res.text();
        const matches = text.match(/"code":"([A-Za-z0-9_-]{11})"/g);
        if (matches) {
          for (const m of matches) {
            const code = m.split(':"')[1].slice(0, 11);
            accReels.add(`https://www.instagram.com/reel/${code}/`);
          }
        }
      } catch (e) {}
    }
  };

  page.on('response', onResponse);

  try {
    // 1. Visit Reels tab
    await page.goto(`https://www.instagram.com/${acc}/reels/`, { waitUntil: 'networkidle2', timeout: 35000 });
    let lastCount = 0;
    let stagnant = 0;

    for (let s = 1; s <= 20; s++) {
      const domLinks = await page.$$eval('a[href*="/reel/"], a[href*="/p/"]', els => els.map(e => e.href));
      domLinks.forEach(u => {
        const m = u.match(/\/(?:reel|p)\/([A-Za-z0-9_-]{11})\//);
        if (m) accReels.add(`https://www.instagram.com/reel/${m[1]}/`);
      });

      console.log(`Scroll ${s} -> Collected ${accReels.size} reels`);
      if (accReels.size === lastCount) {
        stagnant++;
        if (stagnant >= 5) break;
      } else {
        stagnant = 0;
        lastCount = accReels.size;
      }
      await page.evaluate(() => window.scrollBy(0, 2000));
      await new Promise(r => setTimeout(r, 1200));
    }

    // 2. Also visit Main Profile tab
    await page.goto(`https://www.instagram.com/${acc}/`, { waitUntil: 'networkidle2', timeout: 30000 });
    for (let s = 1; s <= 10; s++) {
      const domLinks = await page.$$eval('a[href*="/reel/"], a[href*="/p/"]', els => els.map(e => e.href));
      domLinks.forEach(u => {
        const m = u.match(/\/(?:reel|p)\/([A-Za-z0-9_-]{11})\//);
        if (m) accReels.add(`https://www.instagram.com/reel/${m[1]}/`);
      });
      await page.evaluate(() => window.scrollBy(0, 2000));
      await new Promise(r => setTimeout(r, 1000));
    }
  } catch (err) {
    console.error(`Error:`, err.message);
  } finally {
    page.off('response', onResponse);
  }

  await browser.close();

  const urls = Array.from(accReels);
  console.log(`\n✅ Scraped ${urls.length} unique reels from @${acc}:`);
  urls.forEach(u => console.log(u));

  // Update catalog
  const catalogPath = '/home/samirkhadka/ytbe/roblox_reels_catalog.json';
  let catalog = {};
  if (fs.existsSync(catalogPath)) {
    catalog = JSON.parse(fs.readFileSync(catalogPath, 'utf8'));
  }
  catalog[acc] = urls;
  fs.writeFileSync(catalogPath, JSON.stringify(catalog, null, 2));

  // Update all urls
  const allUrlsPath = '/home/samirkhadka/ytbe/roblox_all_urls.txt';
  const allUrls = new Set();
  for (const k in catalog) {
    catalog[k].forEach(u => allUrls.add(u));
  }
  fs.writeFileSync(allUrlsPath, Array.from(allUrls).join('\n'));

  console.log(`\n🎉 Updated catalog! Total unique reels across all ${Object.keys(catalog).length} accounts: ${allUrls.size}`);
})();
