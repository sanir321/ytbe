const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const ACCOUNTS = [
  'nixuj_playz',
  'robloxstoriesevryday',
  'craftee_films',
  'coo.gae',
  'themiloshoww',
  'ruletopia',
  'moodlyvines',
  'zaylento',
  'stickman.deadzone'
];

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
    userDataDir: '/tmp/insta_roblox_scraper_profile',
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

  const results = {};
  const allUrlsSet = new Set();
  const catalogPath = '/home/samirkhadka/ytbe/roblox_reels_catalog.json';
  const allUrlsPath = '/home/samirkhadka/ytbe/roblox_all_urls.txt';

  // Load existing if present
  if (fs.existsSync(catalogPath)) {
    try {
      const existing = JSON.parse(fs.readFileSync(catalogPath, 'utf8'));
      Object.assign(results, existing);
      for (const acc in existing) {
        existing[acc].forEach(u => allUrlsSet.add(u));
      }
      console.log(`Loaded ${allUrlsSet.size} previously saved Roblox reels across ${Object.keys(results).length} accounts.`);
    } catch (e) {}
  }

  for (const acc of ACCOUNTS) {
    console.log(`\n========================================`);
    console.log(`🚀 Starting scraping for @${acc}...`);
    console.log(`========================================`);

    const accReels = new Set(results[acc] || []);
    let newCaptured = 0;

    const onResponse = async (res) => {
      const url = res.url();
      if (url.includes('graphql') || url.includes('/clips/') || url.includes('/api/v1/')) {
        try {
          const text = await res.text();
          const matches = text.match(/"code":"([A-Za-z0-9_-]{11})"/g);
          if (matches) {
            for (const m of matches) {
              const code = m.split(':"')[1].slice(0, 11);
              const reelUrl = `https://www.instagram.com/reel/${code}/`;
              if (!accReels.has(reelUrl)) {
                accReels.add(reelUrl);
                allUrlsSet.add(reelUrl);
                newCaptured++;
              }
            }
          }
        } catch (e) {}
      }
    };

    page.on('response', onResponse);

    try {
      // 1. Visit Reels tab
      const reelsUrl = `https://www.instagram.com/${acc}/reels/`;
      await page.goto(reelsUrl, { waitUntil: 'networkidle2', timeout: 35000 });

      let stagnant = 0;
      let lastCount = accReels.size;
      const maxScrolls = 40;

      for (let s = 1; s <= maxScrolls; s++) {
        const domLinks = await page.$$eval('a[href*="/reel/"], a[href*="/p/"]', els => els.map(e => e.href));
        domLinks.forEach(u => {
          const m = u.match(/\/(?:reel|p)\/([A-Za-z0-9_-]{11})\//);
          if (m) {
            const reelUrl = `https://www.instagram.com/reel/${m[1]}/`;
            if (!accReels.has(reelUrl)) {
              accReels.add(reelUrl);
              allUrlsSet.add(reelUrl);
              newCaptured++;
            }
          }
        });

        if (s % 5 === 0) {
          console.log(`[@${acc}] Scroll ${s}/${maxScrolls} -> Total: ${accReels.size} reels`);
        }

        if (accReels.size === lastCount) {
          stagnant++;
          if (stagnant >= 6) {
            console.log(`[@${acc}] Bottom of reels tab reached.`);
            break;
          }
        } else {
          stagnant = 0;
          lastCount = accReels.size;
        }

        await page.evaluate(() => window.scrollBy(0, 2200));
        await new Promise(r => setTimeout(r, 1200));
      }

      // 2. Also quickly check main grid for any feed video posts
      console.log(`[@${acc}] Checking main grid for feed videos...`);
      await page.goto(`https://www.instagram.com/${acc}/`, { waitUntil: 'networkidle2', timeout: 30000 });
      for (let s = 1; s <= 15; s++) {
        const domLinks = await page.$$eval('a[href*="/reel/"], a[href*="/p/"]', els => els.map(e => e.href));
        domLinks.forEach(u => {
          const m = u.match(/\/(?:reel|p)\/([A-Za-z0-9_-]{11})\//);
          if (m) {
            const reelUrl = `https://www.instagram.com/reel/${m[1]}/`;
            accReels.add(reelUrl);
            allUrlsSet.add(reelUrl);
          }
        });
        await page.evaluate(() => window.scrollBy(0, 2200));
        await new Promise(r => setTimeout(r, 1000));
      }

    } catch (err) {
      console.error(`[@${acc}] Error scraping:`, err.message);
    } finally {
      page.off('response', onResponse);
    }

    results[acc] = Array.from(accReels);
    console.log(`✅ [@${acc}] Finished! Total videos: ${results[acc].length}`);

    // Persist progress after each account
    fs.writeFileSync(catalogPath, JSON.stringify(results, null, 2));
    fs.writeFileSync(allUrlsPath, Array.from(allUrlsSet).join('\n'));
    console.log(`💾 Saved catalog checkpoint (${allUrlsSet.size} total videos across all accounts).`);
  }

  await browser.close();
  console.log(`\n🎉 ALL 9 ROBLOX ACCOUNTS SCRAPED! Total unique videos: ${allUrlsSet.size}`);
})();
