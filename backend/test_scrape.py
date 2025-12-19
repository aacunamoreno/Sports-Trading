import asyncio
from playwright.async_api import async_playwright

async def test_scrape():
    print("Starting playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Login
        print("Going to login page...")
        await page.goto('https://www.plays888.co/wager/login.aspx', timeout=30000)
        await page.wait_for_timeout(2000)
        
        print("Logging in as jac075...")
        await page.fill('#Login1_UserName', 'jac075')
        await page.fill('#Login1_Password', 'acuna2025!')
        await page.click('#Login1_LoginButton')
        await page.wait_for_timeout(3000)
        
        # Go to History
        print("Going to History page...")
        await page.goto('https://www.plays888.co/wager/History.aspx', timeout=30000)
        await page.wait_for_timeout(4000)
        
        # Take screenshot
        await page.screenshot(path='/app/backend/history_page.png', full_page=True)
        print("Screenshot saved to /app/backend/history_page.png")
        
        # Get page HTML for debugging
        html_content = await page.content()
        with open('/app/backend/history_page.html', 'w') as f:
            f.write(html_content)
        print("HTML saved to /app/backend/history_page.html")
        
        # Try to extract the table
        result = await page.evaluate('''() => {
            const result = {
                tables_found: 0,
                table_texts: [],
                balance_row: null,
                daily_profits: []
            };
            
            const tables = document.querySelectorAll('table');
            result.tables_found = tables.length;
            
            for (const table of tables) {
                const text = table.textContent.substring(0, 500);
                result.table_texts.push(text);
                
                if (text.includes('Beginning Of Week') || (text.includes('lun') && text.includes('mar'))) {
                    const rows = table.querySelectorAll('tr');
                    for (const row of rows) {
                        const rowText = row.textContent;
                        if (rowText.includes('Balance')) {
                            result.balance_row = rowText.substring(0, 300);
                            const cells = row.querySelectorAll('td');
                            const dayNames = ['Beginning', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom', 'Total'];
                            const balances = [];
                            
                            for (let i = 0; i < cells.length && i < dayNames.length; i++) {
                                const cellText = cells[i].textContent.trim();
                                const match = cellText.match(/(-?[\d,]+\.\d+)/);
                                if (match) {
                                    const balance = parseFloat(match[1].replace(/,/g, ''));
                                    balances.push({day: dayNames[i], balance: balance});
                                }
                            }
                            
                            // Calculate profits
                            for (let i = 1; i < balances.length - 1; i++) {
                                const prevBalance = balances[i-1].balance;
                                const currBalance = balances[i].balance;
                                const profit = currBalance - prevBalance;
                                result.daily_profits.push({day: dayNames[i], profit: profit});
                            }
                            break;
                        }
                    }
                    break;
                }
            }
            
            return result;
        }''')
        
        print("Result:", result)
        
        await browser.close()
        print("Done!")

asyncio.run(test_scrape())
