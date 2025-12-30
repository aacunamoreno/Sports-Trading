#!/usr/bin/env python3
"""
Efficient NCAAB PPG scraper using single browser, sequential processing.
"""
import asyncio
import re
import os
from datetime import datetime
from pymongo import MongoClient

client = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
db = client[os.environ.get('DB_NAME', 'test_database')]

async def main():
    from playwright.async_api import async_playwright
    
    today = datetime.now().strftime('%Y-%m-%d')
    date_url = today.replace("-", "")
    
    print(f"[NCAAB PPG] Starting for {today}")
    
    # Get existing data
    existing = db.ncaab_opportunities.find_one({"date": today})
    existing_games = existing.get('games', []) if existing else []
    existing_plays = existing.get('plays', []) if existing else []
    
    print(f"[NCAAB PPG] Found {len(existing_games)} games, {len(existing_plays)} plays")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Step 1: Get team URLs from scoreboard
        print("[NCAAB PPG] Fetching scoreboard...")
        url = f"https://www.cbssports.com/college-basketball/scoreboard/FBS/{date_url}/?layout=compact"
        page = await browser.new_page()
        await page.goto(url, timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)
        
        data = await page.evaluate("""() => {
            const teamUrls = {};
            const links = document.querySelectorAll('a[href*="/college-basketball/teams/"]');
            links.forEach(a => {
                const href = a.getAttribute('href');
                let name = a.innerText.trim().replace(/^\\d+\\s*/, '').split('\\n')[0].trim();
                if (name && name.length > 1 && name.length < 30 && href) {
                    teamUrls[name] = href;
                }
            });
            return teamUrls;
        }""")
        await page.close()
        
        team_urls = data
        print(f"[NCAAB PPG] Found {len(team_urls)} team URLs")
        
        # Step 2: Scrape each team sequentially
        team_stats = {}
        teams_list = list(team_urls.items())
        
        for i, (team_name, team_url) in enumerate(teams_list):
            try:
                full_url = f"https://www.cbssports.com{team_url}"
                page = await browser.new_page()
                await page.goto(full_url, timeout=15000)
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(800)
                
                content = await page.evaluate("""() => {
                    const body = document.body.innerText;
                    const idx = body.indexOf('Schedule');
                    if (idx > -1) return body.substring(idx, idx + 1500);
                    return body.substring(0, 1500);
                }""")
                await page.close()
                
                # Parse scores
                scores = []
                for match in re.finditer(r'\b([WL])\s+(\d+)-(\d+)\b', content):
                    result, s1, s2 = match.groups()
                    team_score = int(s1) if result == 'W' else int(s2)
                    if 40 <= team_score <= 150:
                        scores.append(team_score)
                
                if scores:
                    last3 = scores[-3:] if len(scores) >= 3 else scores
                    team_stats[team_name] = {
                        'last3_avg': round(sum(last3) / len(last3), 1),
                        'last3_scores': last3
                    }
                
                if (i + 1) % 10 == 0:
                    print(f"[NCAAB PPG]   {i+1}/{len(teams_list)} teams ({len(team_stats)} with data)")
                    
            except Exception as e:
                pass  # Skip failed teams silently
        
        await browser.close()
    
    print(f"[NCAAB PPG] Got Last 3 PPG for {len(team_stats)} teams")
    
    # Build lookups
    last3_values = {n: s['last3_avg'] for n, s in team_stats.items()}
    sorted_teams = sorted(last3_values.items(), key=lambda x: x[1], reverse=True)
    last3_ranks = {n: r for r, (n, _) in enumerate(sorted_teams, 1)}
    
    def find(name, d):
        if not name: return None
        if name in d: return d[name]
        nl = name.lower()
        for k, v in d.items():
            if k.lower() == nl or nl in k.lower() or k.lower() in nl:
                return v
        return None
    
    def dot(rank):
        if rank is None: return '⚪'
        if rank <= 50: return '🟢'
        if rank <= 100: return '🔵'
        if rank <= 150: return '🟡'
        return '🔴'
    
    # Update games
    updated_games = []
    count = 0
    
    for i, game in enumerate(existing_games, 1):
        away = game.get('away_team', '')
        home = game.get('home_team', '')
        
        away_ppg = find(away, last3_values)
        home_ppg = find(home, last3_values)
        away_rank = find(away, last3_ranks)
        home_rank = find(home, last3_ranks)
        
        combined = round(away_ppg + home_ppg, 1) if away_ppg and home_ppg else None
        if combined: count += 1
        
        line = game.get('total') or game.get('opening_line')
        edge = round(combined - float(line), 1) if combined and line else None
        
        rec = ''
        if edge:
            if edge >= 9: rec = 'OVER'
            elif edge <= -9: rec = 'UNDER'
        
        updated_games.append({
            **game,
            'game_num': i,
            'away_last3_value': away_ppg, 'away_ppg_value': away_ppg,
            'away_last3_rank': away_rank, 'away_ppg_rank': away_rank,
            'home_last3_value': home_ppg, 'home_ppg_value': home_ppg,
            'home_last3_rank': home_rank, 'home_ppg_rank': home_rank,
            'combined_ppg': combined, 'edge': edge, 'recommendation': rec,
            'away_dots': dot(away_rank)*2, 'home_dots': dot(home_rank)*2
        })
    
    # Save
    db.ncaab_opportunities.update_one(
        {"date": today},
        {"$set": {
            "games": updated_games,
            "plays": existing_plays,
            "last_updated": datetime.now().strftime('%I:%M %p'),
            "data_source": "cbssports.com (Last 3 PPG)",
            "ppg_locked": True
        }},
        upsert=True
    )
    
    print(f"[NCAAB PPG] DONE! Updated {count}/{len(updated_games)} games")

if __name__ == "__main__":
    asyncio.run(main())
