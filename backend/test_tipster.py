import asyncio
import sys
sys.path.insert(0, '/app/backend')

from playwright.async_api import async_playwright

async def test_tipster():
    print("Testing TIPSTER (jac083) account...")
    
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
    
    # Navigate to login page
    print("Navigating to plays888.co...")
    await page.goto('https://www.plays888.co', timeout=30000)
    await page.wait_for_timeout(2000)
    
    # Login 
    try:
        await page.wait_for_selector('input[type="text"], input[name*="user"], input[name*="login"]', timeout=5000)
        await page.fill('input[type="text"], input[name*="user"], input[name*="login"]', 'jac083')
        await page.fill('input[type="password"]', 'acuna2025!')
        await page.click('button[type="submit"], input[type="submit"], button:has-text("Acceder")')
        await page.wait_for_timeout(3000)
        print(f"Login submitted, URL: {page.url}")
    except Exception as e:
        print(f"Login error: {e}")
    
    # Navigate to History
    print("Navigating to History page...")
    await page.goto('https://www.plays888.co/wager/History.aspx', timeout=30000)
    await page.wait_for_timeout(4000)
    
    # Take screenshot
    await page.screenshot(path='/app/backend/tipster_history.png')
    print("Screenshot saved: tipster_history.png")
    
    # Get raw table data
    result = await page.evaluate('''() => {
        const result = {
            tables_found: 0,
            table_texts: [],
            all_rows: []
        };
        
        const tables = document.querySelectorAll('table');
        result.tables_found = tables.length;
        
        for (const table of tables) {
            const text = table.textContent.trim();
            result.table_texts.push(text.substring(0, 400));
            
            if (text.includes('Beginning Of Week') || (text.includes('lun') && text.includes('mar') && text.includes('jue'))) {
                const rows = table.querySelectorAll('tr');
                for (const row of rows) {
                    const cells = Array.from(row.querySelectorAll('td'));
                    const rowData = cells.map(c => c.textContent.trim());
                    result.all_rows.push(rowData);
                }
                break;
            }
        }
        
        return result;
    }''')
    
    print(f"Tables found: {result['tables_found']}")
    print("Raw rows:")
    for row in result['all_rows']:
        print(f"  {row}")
    
    await browser.close()
    await playwright.stop()
    print("Done!")

asyncio.run(test_tipster())
