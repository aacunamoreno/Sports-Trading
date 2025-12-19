import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright

async def verify():
    # Check Arizona time
    arizona_tz = ZoneInfo('America/Phoenix')
    now = datetime.now(arizona_tz)
    print(f"Current Arizona time: {now}")
    print(f"Day of week: {now.strftime('%A')}")
    
    day_map = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    today_day = day_map[now.weekday()]
    print(f"Today (normalized): {today_day}")
    
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True,
        args=['--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage', '--no-sandbox']
    )
    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    page = await context.new_page()
    
    # Test with ENANO account
    await page.goto('https://www.plays888.co', timeout=30000)
    await page.wait_for_timeout(2000)
    await page.wait_for_selector('input[type="text"], input[name*="user"], input[name*="login"]', timeout=5000)
    await page.fill('input[type="text"], input[name*="user"], input[name*="login"]', 'jac075')
    await page.fill('input[type="password"]', 'acuna2025!')
    await page.click('button[type="submit"], input[type="submit"], button:has-text("Acceder")')
    await page.wait_for_timeout(3000)
    
    await page.goto('https://www.plays888.co/wager/History.aspx', timeout=30000)
    await page.wait_for_timeout(4000)
    
    # Get the raw data
    data = await page.evaluate('''() => {
        const tables = document.querySelectorAll('table');
        for (const table of tables) {
            const text = table.textContent.toLowerCase();
            if (text.includes('beginning') || (text.includes('lun') && text.includes('mar'))) {
                const rows = table.querySelectorAll('tr');
                const result = {};
                
                // Get header
                const headerRow = rows[0];
                if (headerRow) {
                    result.header = Array.from(headerRow.querySelectorAll('td, th')).map(c => c.textContent.trim());
                }
                
                // Get Win/Loss row
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length > 0 && cells[0].textContent.toLowerCase().includes('win')) {
                        result.winloss = Array.from(cells).map(c => c.textContent.trim());
                        break;
                    }
                }
                
                return result;
            }
        }
        return null;
    }''')
    
    print("\n=== ENANO (jac075) Raw Data ===")
    print(f"Header: {data['header']}")
    print(f"Win/Loss: {data['winloss']}")
    
    # Map header to win/loss
    print("\n=== Day-to-Value Mapping ===")
    for i, header in enumerate(data['header']):
        winloss = data['winloss'][i] if i < len(data['winloss']) else 'N/A'
        print(f"  Index {i}: Header='{header}' -> Value='{winloss}'")
    
    await browser.close()
    await playwright.stop()

asyncio.run(verify())
