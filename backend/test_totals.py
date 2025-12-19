import asyncio
import sys
sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

async def test_totals():
    print("Starting Plays888Service test...")
    
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
    
    # Take screenshot to debug
    await page.screenshot(path='/app/backend/step1_main.png')
    print("Screenshot saved: step1_main.png")
    
    # Login 
    print("Looking for login form...")
    try:
        await page.wait_for_selector('input[type="text"], input[name*="user"], input[name*="login"]', timeout=5000)
        await page.fill('input[type="text"], input[name*="user"], input[name*="login"]', 'jac075')
        await page.fill('input[type="password"]', 'acuna2025!')
        await page.click('button[type="submit"], input[type="submit"], button:has-text("Acceder")')
        await page.wait_for_timeout(3000)
        print("Login submitted")
    except Exception as e:
        print(f"Login error: {e}")
    
    # Take screenshot after login
    await page.screenshot(path='/app/backend/step2_after_login.png')
    print("Screenshot saved: step2_after_login.png")
    
    # Check URL
    print(f"Current URL: {page.url}")
    
    # Navigate to History
    print("Navigating to History page...")
    await page.goto('https://www.plays888.co/wager/History.aspx', timeout=30000)
    await page.wait_for_timeout(4000)
    
    # Take screenshot
    await page.screenshot(path='/app/backend/step3_history.png')
    print("Screenshot saved: step3_history.png")
    
    # Try to extract data
    result = await page.evaluate('''() => {
        const result = {
            tables_found: 0,
            sample_texts: [],
            balance_data: null
        };
        
        const tables = document.querySelectorAll('table');
        result.tables_found = tables.length;
        
        for (const table of tables) {
            const text = table.textContent.trim();
            result.sample_texts.push(text.substring(0, 300));
            
            if (text.includes('Beginning Of Week') || (text.includes('lun') && text.includes('mar') && text.includes('jue'))) {
                const rows = table.querySelectorAll('tr');
                for (const row of rows) {
                    const rowText = row.textContent;
                    if (rowText.includes('Balance')) {
                        result.balance_data = rowText.substring(0, 500);
                        break;
                    }
                }
                break;
            }
        }
        
        return result;
    }''')
    
    print(f"Tables found: {result['tables_found']}")
    print(f"Balance data: {result['balance_data']}")
    print("Sample texts:")
    for i, txt in enumerate(result['sample_texts'][:5]):
        print(f"  Table {i}: {txt[:150]}...")
    
    await browser.close()
    await playwright.stop()
    print("Done!")

asyncio.run(test_totals())
