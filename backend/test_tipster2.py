import asyncio
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
    await page.goto('https://www.plays888.co', timeout=30000)
    await page.wait_for_timeout(2000)
    
    # Login 
    await page.wait_for_selector('input[type="text"], input[name*="user"], input[name*="login"]', timeout=5000)
    await page.fill('input[type="text"], input[name*="user"], input[name*="login"]', 'jac083')
    await page.fill('input[type="password"]', 'acuna2025!')
    await page.click('button[type="submit"], input[type="submit"], button:has-text("Acceder")')
    await page.wait_for_timeout(3000)
    
    # Navigate to History
    await page.goto('https://www.plays888.co/wager/History.aspx', timeout=30000)
    await page.wait_for_timeout(4000)
    
    # Get ALL table content
    result = await page.evaluate('''() => {
        const result = [];
        const tables = document.querySelectorAll('table');
        
        for (let i = 0; i < tables.length; i++) {
            const table = tables[i];
            const rows = table.querySelectorAll('tr');
            const tableData = {
                idx: i,
                rows: []
            };
            
            for (const row of rows) {
                const cells = Array.from(row.querySelectorAll('td, th'));
                const rowData = cells.map(c => c.textContent.trim());
                if (rowData.length > 0) {
                    tableData.rows.push(rowData);
                }
            }
            
            result.push(tableData);
        }
        
        return result;
    }''')
    
    print(f"Total tables: {len(result)}")
    for table in result:
        print(f"\nTable {table['idx']}:")
        for row in table['rows'][:10]:
            print(f"  {row}")
    
    await browser.close()
    await playwright.stop()

asyncio.run(test_tipster())
