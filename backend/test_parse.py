import asyncio
import sys
sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

async def test_parse():
    print("Starting detailed parsing test...")
    
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
        await page.fill('input[type="text"], input[name*="user"], input[name*="login"]', 'jac075')
        await page.fill('input[type="password"]', 'acuna2025!')
        await page.click('button[type="submit"], input[type="submit"], button:has-text("Acceder")')
        await page.wait_for_timeout(3000)
        print("Login successful")
    except Exception as e:
        print(f"Login error: {e}")
    
    # Navigate to History
    print("Navigating to History page...")
    await page.goto('https://www.plays888.co/wager/History.aspx', timeout=30000)
    await page.wait_for_timeout(4000)
    
    # Improved parsing
    result = await page.evaluate('''() => {
        const result = {
            daily_profits: [],
            week_total: null,
            win_loss_row: [],
            balance_row: [],
            raw_data: null,
            error: null
        };
        
        try {
            const tables = document.querySelectorAll('table');
            
            for (const table of tables) {
                const text = table.textContent.trim();
                
                if (text.includes('Beginning Of Week') || (text.includes('lun') && text.includes('mar') && text.includes('jue'))) {
                    const rows = table.querySelectorAll('tr');
                    const dayNames = ['Beginning', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom', 'Total'];
                    
                    for (const row of rows) {
                        const cells = row.querySelectorAll('td');
                        if (cells.length < 2) continue;
                        
                        const firstCell = cells[0].textContent.trim().toLowerCase();
                        
                        // Win/Loss row - THIS HAS THE DAILY PROFITS DIRECTLY!
                        if (firstCell.includes('win') || firstCell.includes('loss')) {
                            for (let i = 1; i < cells.length && i <= 8; i++) {
                                const cellText = cells[i].textContent.trim();
                                const match = cellText.match(/(-?[\\d,]+\\.\\d+)/);
                                if (match) {
                                    const profit = parseFloat(match[1].replace(/,/g, ''));
                                    result.win_loss_row.push({
                                        day: dayNames[i],
                                        profit: profit
                                    });
                                }
                            }
                        }
                        
                        // Balance row
                        if (firstCell.includes('balance')) {
                            for (let i = 1; i < cells.length && i <= 8; i++) {
                                const cellText = cells[i].textContent.trim();
                                const match = cellText.match(/(-?[\\d,]+\\.\\d+)/);
                                if (match) {
                                    const balance = parseFloat(match[1].replace(/,/g, ''));
                                    result.balance_row.push({
                                        day: dayNames[i],
                                        balance: balance
                                    });
                                }
                            }
                        }
                    }
                    
                    // Use Win/Loss row directly for daily profits
                    if (result.win_loss_row.length > 0) {
                        result.daily_profits = result.win_loss_row.filter(d => d.day !== 'Total');
                        const total = result.win_loss_row.find(d => d.day === 'Total');
                        if (total) {
                            result.week_total = total.profit;
                        } else {
                            result.week_total = result.daily_profits.reduce((sum, d) => sum + d.profit, 0);
                        }
                    }
                    
                    break;
                }
            }
        } catch (e) {
            result.error = e.toString();
        }
        
        return result;
    }''')
    
    print(f"Daily Profits: {result['daily_profits']}")
    print(f"Week Total: {result['week_total']}")
    print(f"Win/Loss row: {result['win_loss_row']}")
    print(f"Balance row: {result['balance_row']}")
    if result.get('error'):
        print(f"Error: {result['error']}")
    
    await browser.close()
    await playwright.stop()
    print("Done!")

asyncio.run(test_parse())
