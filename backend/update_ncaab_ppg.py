#!/usr/bin/env python3
"""
NCAAB PPG scraper - scrapes ONLY teams playing on the target date.
Uses TARGET_DATE env var (defaults to tomorrow if not set).
"""
import asyncio
import re
import os
from datetime import datetime, timedelta
from pymongo import MongoClient

client = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
db = client[os.environ.get('DB_NAME', 'test_database')]

async def main():
    from playwright.async_api import async_playwright
    
    # Get target date from environment or default to tomorrow
    target_date = os.environ.get('TARGET_DATE')
    if not target_date:
        target_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    date_url = target_date.replace("-", "")
    
    print(f"[NCAAB PPG] Starting for {target_date}")
    
    # Get existing games from database
    existing = db.ncaab_opportunities.find_one({"date": target_date})
    existing_games = existing.get('games', []) if existing else []
    existing_plays = existing.get('plays', []) if existing else []
    
    print(f"[NCAAB PPG] Found {len(existing_games)} games, {len(existing_plays)} plays")
    
    if not existing_games:
        print("[NCAAB PPG] No games found. Please refresh NCAAB first.")
        return
    
    # Get unique teams from today's games
    teams_needed = set()
    for game in existing_games:
        teams_needed.add(game.get('away_team', ''))
        teams_needed.add(game.get('home_team', ''))
    teams_needed.discard('')
    
    print(f"[NCAAB PPG] Need PPG for {len(teams_needed)} teams")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Get team URLs from scoreboard
        print("[NCAAB PPG] Fetching team URLs from scoreboard...")
        url = f"https://www.cbssports.com/college-basketball/scoreboard/FBS/{date_url}/?layout=compact"
        page = await browser.new_page()
        await page.goto(url, timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)
        
        all_team_urls = await page.evaluate("""() => {
            const teamUrls = {};
            const links = document.querySelectorAll('a[href*="/college-basketball/teams/"]');
            links.forEach(a => {
                const href = a.getAttribute('href');
                let name = a.innerText.trim().replace(/^\\d+\\s*/, '').split('\\n')[0].trim();
                if (name && name.length > 1 && name.length < 35 && href) {
                    teamUrls[name] = href;
                }
            });
            return teamUrls;
        }""")
        await page.close()
        
        print(f"[NCAAB PPG] Found {len(all_team_urls)} team URLs on scoreboard")
        
        # Match teams we need to URLs (fuzzy match)
        team_urls = {}
        for team in teams_needed:
            team_lower = team.lower()
            for url_team, url in all_team_urls.items():
                url_team_lower = url_team.lower()
                if team_lower == url_team_lower or team_lower in url_team_lower or url_team_lower in team_lower:
                    team_urls[team] = url
                    break
        
        print(f"[NCAAB PPG] Matched {len(team_urls)}/{len(teams_needed)} teams to URLs")
        
        # Scrape each team
        team_stats = {}
        teams_list = list(team_urls.items())
        
        for i, (team_name, team_url) in enumerate(teams_list):
            try:
                full_url = f"https://www.cbssports.com{team_url}"
                page = await browser.new_page()
                await page.goto(full_url, timeout=12000)
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(600)
                
                content = await page.evaluate("""() => {
                    const body = document.body.innerText;
                    const idx = body.indexOf('Schedule');
                    if (idx > -1) return body.substring(idx, idx + 1200);
                    return body.substring(0, 1200);
                }""")
                await page.close()
                
                # Parse scores: W 80-71 or L 58-80
                scores = []
                for match in re.finditer(r'\b([WL])\s+(\d+)-(\d+)\b', content):
                    result, s1, s2 = match.groups()
                    team_score = int(s1) if result == 'W' else int(s2)
                    if 40 <= team_score <= 160:
                        scores.append(team_score)
                
                if scores:
                    last3 = scores[-3:] if len(scores) >= 3 else scores
                    avg = round(sum(last3) / len(last3), 1)
                    team_stats[team_name] = {'last3_avg': avg, 'scores': last3}
                    print(f"  {team_name}: {last3} -> avg {avg}")
                else:
                    print(f"  {team_name}: No scores found")
                    
            except Exception as e:
                print(f"  {team_name}: Error - {str(e)[:50]}")
        
        await browser.close()
    
    print(f"\n[NCAAB PPG] Got Last 3 PPG for {len(team_stats)} teams")
    
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
        total = len(last3_ranks)
        if total == 0: return '⚪'
        pct = rank / total
        if pct <= 0.25: return '🟢'
        if pct <= 0.50: return '🔵'
        if pct <= 0.75: return '🟡'
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
        
        combined = round(away_ppg + home_ppg, 1) if away_ppg and home_ppg else game.get('combined_ppg')
        if away_ppg and home_ppg: count += 1
        
        line = game.get('total') or game.get('opening_line')
        edge = round(combined - float(line), 1) if combined and line else game.get('edge')
        
        rec = game.get('recommendation', '')
        if edge:
            if edge >= 9: rec = 'OVER'
            elif edge <= -9: rec = 'UNDER'
            else: rec = ''
        
        updated_games.append({
            **game,
            'game_num': i,
            'away_last3_value': away_ppg or game.get('away_last3_value'),
            'away_ppg_value': away_ppg or game.get('away_ppg_value'),
            'away_last3_rank': away_rank or game.get('away_last3_rank'),
            'away_ppg_rank': away_rank or game.get('away_ppg_rank'),
            'home_last3_value': home_ppg or game.get('home_last3_value'),
            'home_ppg_value': home_ppg or game.get('home_ppg_value'),
            'home_last3_rank': home_rank or game.get('home_last3_rank'),
            'home_ppg_rank': home_rank or game.get('home_ppg_rank'),
            'combined_ppg': combined,
            'edge': edge,
            'recommendation': rec,
            'away_dots': (dot(away_rank) if away_rank else game.get('away_dots', '⚪⚪'))[:2],
            'home_dots': (dot(home_rank) if home_rank else game.get('home_dots', '⚪⚪'))[:2]
        })
    
    # Save
    db.ncaab_opportunities.update_one(
        {"date": target_date},
        {"$set": {
            "games": updated_games,
            "plays": existing_plays,
            "last_updated": datetime.now().strftime('%I:%M %p'),
            "data_source": "cbssports.com (Last 3 PPG)",
            "ppg_locked": True
        }},
        upsert=True
    )
    
    print(f"\n[NCAAB PPG] DONE! Updated {count}/{len(updated_games)} games with new PPG")
    print(f"[NCAAB PPG] Plays preserved: {len(existing_plays)}")

if __name__ == "__main__":
    asyncio.run(main())
