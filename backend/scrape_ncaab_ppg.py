#!/usr/bin/env python3
"""
Standalone script to scrape NCAAB Last 3 PPG from CBS Sports.
This script runs outside the main server to avoid memory issues.
"""
import asyncio
import re
import os
import sys
from datetime import datetime
from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
db = client[os.environ.get('DB_NAME', 'test_database')]

async def scrape_ncaab_ppg():
    """Scrape NCAAB Last 3 PPG from CBS Sports team pages."""
    from playwright.async_api import async_playwright
    
    today = datetime.now().strftime('%Y-%m-%d')
    date_for_url = today.replace("-", "")
    url = f"https://www.cbssports.com/college-basketball/scoreboard/FBS/{date_for_url}/?layout=compact"
    
    print(f"[NCAAB PPG] Starting scrape for {today}")
    print(f"[NCAAB PPG] URL: {url}")
    
    team_urls = {}
    games_data = []
    team_stats = {}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Step 1: Get games and team URLs from scoreboard
        print("[NCAAB PPG] Step 1: Scraping scoreboard for games and team URLs...")
        page = await browser.new_page()
        await page.goto(url, timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(3000)
        
        data = await page.evaluate("""() => {
            const games = [];
            const teamUrls = {};
            const cards = document.querySelectorAll('.single-score-card');
            
            cards.forEach((card) => {
                try {
                    const teamLinks = card.querySelectorAll('a[href*="/college-basketball/teams/"]');
                    const teams = [];
                    
                    teamLinks.forEach(a => {
                        const href = a.getAttribute('href');
                        const teamSpan = a.querySelector('.team-location-name, .team');
                        let name = teamSpan ? teamSpan.innerText.trim() : a.innerText.trim();
                        name = name.replace(/^\\d+\\s*/, '').split('\\n')[0].trim();
                        
                        if (name && name.length > 1 && name.length < 30 && href && href.includes('/teams/')) {
                            teams.push({ name: name, url: href });
                            teamUrls[name] = href;
                        }
                    });
                    
                    if (teams.length >= 2) {
                        const rawText = card.innerText;
                        let total = null;
                        const totalMatch = rawText.match(/o(\\d+\\.?\\d*)/);
                        if (totalMatch) total = parseFloat(totalMatch[1]);
                        
                        let time = '';
                        const lines = rawText.split('\\n');
                        for (const line of lines) {
                            if (/^\\d+:\\d+\\s*(AM|PM)?/i.test(line.trim())) {
                                time = line.trim();
                                break;
                            }
                        }
                        
                        games.push({
                            away_team: teams[0].name,
                            away_url: teams[0].url,
                            home_team: teams[teams.length - 1].name,
                            home_url: teams[teams.length - 1].url,
                            total: total,
                            time: time
                        });
                    }
                } catch(e) {}
            });
            
            return { games: games, teamUrls: teamUrls };
        }""")
        
        await page.close()
        
        games_data = data['games']
        team_urls = data['teamUrls']
        
        print(f"[NCAAB PPG] Found {len(games_data)} games, {len(team_urls)} teams")
        
        # Step 2: Scrape Last 3 PPG for each team (sequentially to save memory)
        print("[NCAAB PPG] Step 2: Scraping Last 3 PPG for each team...")
        
        teams_list = list(team_urls.items())
        total_teams = len(teams_list)
        
        for i, (team_name, team_url) in enumerate(teams_list):
            try:
                full_url = f"https://www.cbssports.com{team_url}"
                page = await browser.new_page()
                await page.goto(full_url, timeout=15000)
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(500)
                
                # Get schedule section text
                schedule_text = await page.evaluate("""() => {
                    const body = document.body.innerText;
                    const scheduleStart = body.indexOf('Schedule');
                    const scheduleEnd = body.indexOf('Full Schedule');
                    if (scheduleStart > -1 && scheduleEnd > -1) {
                        return body.substring(scheduleStart, scheduleEnd);
                    }
                    return body.substring(0, 2000);
                }""")
                
                await page.close()
                
                # Parse completed games
                completed_scores = []
                for line in schedule_text.split('\n'):
                    match = re.search(r'\b([WL])\s+(\d+)-(\d+)\b', line)
                    if match:
                        result = match.group(1)
                        score1 = int(match.group(2))
                        score2 = int(match.group(3))
                        team_score = score1 if result == 'W' else score2
                        completed_scores.append(team_score)
                
                # Get last 3 scores
                if completed_scores:
                    last3 = completed_scores[-3:] if len(completed_scores) >= 3 else completed_scores
                    last3.reverse()
                    
                    team_stats[team_name] = {
                        'last3_scores': last3,
                        'last3_avg': round(sum(last3) / len(last3), 1),
                        'games_played': len(completed_scores)
                    }
                
                if (i + 1) % 10 == 0:
                    print(f"[NCAAB PPG]   Scraped {i+1}/{total_teams} teams...")
                    
            except Exception as e:
                print(f"[NCAAB PPG]   Error scraping {team_name}: {e}")
        
        await browser.close()
    
    print(f"[NCAAB PPG] Got Last 3 PPG for {len(team_stats)} teams")
    
    # Step 3: Build PPG lookup and update database
    print("[NCAAB PPG] Step 3: Updating database...")
    
    last3_ppg_values = {name: stats['last3_avg'] for name, stats in team_stats.items()}
    
    # Create ranks
    sorted_teams = sorted(last3_ppg_values.items(), key=lambda x: x[1], reverse=True)
    last3_ppg_ranks = {name: rank for rank, (name, _) in enumerate(sorted_teams, 1)}
    
    # Get existing data
    existing = db.ncaab_opportunities.find_one({"date": today})
    existing_games = existing.get('games', []) if existing else []
    existing_plays = existing.get('plays', []) if existing else []
    
    # Fuzzy matching
    def find_value(team_name, data_dict):
        if not team_name:
            return None
        if team_name in data_dict:
            return data_dict[team_name]
        team_lower = team_name.lower()
        for k, v in data_dict.items():
            if k.lower() == team_lower or team_lower in k.lower() or k.lower() in team_lower:
                return v
        return None
    
    def get_dot_color(rank):
        if rank is None:
            return '⚪'
        if rank <= 50:
            return '🟢'
        elif rank <= 100:
            return '🔵'
        elif rank <= 150:
            return '🟡'
        return '🔴'
    
    # Update games
    updated_games = []
    games_updated = 0
    
    source_games = existing_games if existing_games else games_data
    
    for i, game in enumerate(source_games, 1):
        away_team = game.get('away_team', game.get('away', ''))
        home_team = game.get('home_team', game.get('home', ''))
        
        away_ppg = find_value(away_team, last3_ppg_values)
        home_ppg = find_value(home_team, last3_ppg_values)
        away_rank = find_value(away_team, last3_ppg_ranks)
        home_rank = find_value(home_team, last3_ppg_ranks)
        
        combined_ppg = None
        if away_ppg and home_ppg:
            combined_ppg = round(away_ppg + home_ppg, 1)
            games_updated += 1
        
        line = game.get('total') or game.get('opening_line')
        edge = round(combined_ppg - float(line), 1) if combined_ppg and line else None
        
        recommendation = ''
        if edge is not None:
            if edge >= 9:
                recommendation = 'OVER'
            elif edge <= -9:
                recommendation = 'UNDER'
        
        away_dots = get_dot_color(away_rank) + get_dot_color(away_rank)
        home_dots = get_dot_color(home_rank) + get_dot_color(home_rank)
        
        updated_game = {
            **game,
            'game_num': i,
            'away_team': away_team,
            'home_team': home_team,
            'away_last3_value': away_ppg,
            'away_last3_rank': away_rank,
            'away_ppg_value': away_ppg,
            'away_ppg_rank': away_rank,
            'home_last3_value': home_ppg,
            'home_last3_rank': home_rank,
            'home_ppg_value': home_ppg,
            'home_ppg_rank': home_rank,
            'combined_ppg': combined_ppg,
            'edge': edge,
            'recommendation': recommendation,
            'away_dots': away_dots,
            'home_dots': home_dots
        }
        updated_games.append(updated_game)
    
    # Save to database
    from datetime import datetime as dt
    db.ncaab_opportunities.update_one(
        {"date": today},
        {"$set": {
            "date": today,
            "games": updated_games,
            "plays": existing_plays,
            "last_updated": dt.now().strftime('%I:%M %p'),
            "data_source": "cbssports.com (Last 3 PPG)",
            "ppg_locked": True
        }},
        upsert=True
    )
    
    print(f"[NCAAB PPG] Complete! Updated {games_updated}/{len(updated_games)} games")
    print(f"[NCAAB PPG] Plays preserved: {len(existing_plays)}")

if __name__ == "__main__":
    asyncio.run(scrape_ncaab_ppg())
