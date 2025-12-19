import asyncio
from playwright.async_api import async_playwright

async def debug():
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
    
    await page.goto('https://www.plays888.co', timeout=30000)
    await page.wait_for_timeout(2000)
    
    await page.wait_for_selector('input[type="text"], input[name*="user"], input[name*="login"]', timeout=5000)
    await page.fill('input[type="text"], input[name*="user"], input[name*="login"]', 'jac075')
    await page.fill('input[type="password"]', 'acuna2025!')
    await page.click('button[type="submit"], input[type="submit"], button:has-text("Acceder")')
    await page.wait_for_timeout(3000)
    
    await page.goto('https://www.plays888.co/wager/History.aspx', timeout=30000)
    await page.wait_for_timeout(4000)
    
    # Get header row structure
    result = await page.evaluate('''() => {
        const tables = document.querySelectorAll('table');
        
        for (const table of tables) {
            const text = table.textContent.toLowerCase();
            if (text.includes('beginning') || (text.includes('lun') && text.includes('mar'))) {
                const rows = table.querySelectorAll('tr');
                const result = {header: [], win_loss: []};
                
                // First row (header)
                const firstRow = rows[0];
                if (firstRow) {
                    const cells = firstRow.querySelectorAll('td, th');
                    result.header = Array.from(cells).map(c => c.textContent.trim());
                }
                
                // Win/Loss row
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length > 0 && cells[0].textContent.toLowerCase().includes('win')) {
                        result.win_loss = Array.from(cells).map(c => c.textContent.trim());
                        break;
                    }
                }
                
                return result;
            }
        }
        return null;
    }''')
    
    print("Header row:", result['header'])
    print("Win/Loss row:", result['win_loss'])
    print(f"Header length: {len(result['header'])}")
    print(f"Win/Loss length: {len(result['win_loss'])}")
    
    await browser.close()
    await playwright.stop()

asyncio.run(debug())
