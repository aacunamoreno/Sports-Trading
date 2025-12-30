#!/usr/bin/env python3
"""
Lightweight NCAAB PPG scraper using httpx instead of Playwright.
"""
import asyncio
import httpx
import re
import os
from datetime import datetime
from bs4 import BeautifulSoup
from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
db = client[os.environ.get('DB_NAME', 'test_database')]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

async def scrape_team_last3(client: httpx.AsyncClient, team_name: str, team_url: str) -> tuple:
    """Scrape a single team's Last 3 scores using httpx."""
    try:
        full_url = f"https://www.cbssports.com{team_url}"
        response = await client.get(full_url, timeout=10.0)
        
        if response.status_code != 200:
            return team_name, None
        
        html = response.text
        
        # Parse completed games using regex on HTML
        # Look for patterns like "W 83-69" or "L 58-80"
        completed_scores = []
        matches = re.findall(r'\b([WL])\s+(\d+)-(\d+)\b', html)
        
        for match in matches:
            result, score1, score2 = match
            score1, score2 = int(score1), int(score2)
            # W = team won, their score is LEFT; L = team lost, their score is RIGHT
            team_score = score1 if result == 'W' else score2
            if 40 <= team_score <= 150:  # Reasonable basketball score range
                completed_scores.append(team_score)
        
        if completed_scores:
            # Get last 3 unique scores (avoid duplicates from HTML)
            seen = []
            for score in completed_scores:
                if score not in seen[-5:]:  # Allow some repetition but not consecutive
                    seen.append(score)
            
            last3 = seen[-3:] if len(seen) >= 3 else seen
            if last3:
                return team_name, {
                    'last3_scores': last3,
                    'last3_avg': round(sum(last3) / len(last3), 1)
                }
        
        return team_name, None
        
    except Exception as e:
        return team_name, None

async def main():
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"[NCAAB PPG] Starting for {today}")
    
    # Get existing data from database
    existing = db.ncaab_opportunities.find_one({"date": today})
    existing_games = existing.get('games', []) if existing else []
    existing_plays = existing.get('plays', []) if existing else []
    
    print(f"[NCAAB PPG] Found {len(existing_games)} existing games, {len(existing_plays)} plays")
    
    if not existing_games:
        print("[NCAAB PPG] No games in database. Please refresh NCAAB first.")
        return
    
    # Collect unique teams
    teams_to_scrape = {}
    for game in existing_games:
        away = game.get('away_team', '')
        home = game.get('home_team', '')
        away_url = game.get('away_url', '')
        home_url = game.get('home_url', '')
        
        if away and away_url:
            teams_to_scrape[away] = away_url
        if home and home_url:
            teams_to_scrape[home] = home_url
    
    # If no URLs in games, we need to scrape scoreboard first
    if not teams_to_scrape:
        print("[NCAAB PPG] No team URLs found. Scraping CBS scoreboard...")
        date_url = today.replace("-", "")
        url = f"https://www.cbssports.com/college-basketball/scoreboard/FBS/{date_url}/?layout=compact"
        
        async with httpx.AsyncClient(headers=HEADERS) as client:
            response = await client.get(url, timeout=30.0)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find team links
            for link in soup.find_all('a', href=re.compile(r'/college-basketball/teams/')):
                href = link.get('href', '')
                name = link.get_text(strip=True)
                name = re.sub(r'^\d+\s*', '', name).split('\n')[0].strip()
                if name and len(name) > 1 and len(name) < 30:
                    teams_to_scrape[name] = href
    
    print(f"[NCAAB PPG] Scraping {len(teams_to_scrape)} teams...")
    
    # Scrape teams in batches
    team_stats = {}
    teams_list = list(teams_to_scrape.items())
    
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        batch_size = 10
        for i in range(0, len(teams_list), batch_size):
            batch = teams_list[i:i+batch_size]
            tasks = [scrape_team_last3(client, name, url) for name, url in batch]
            results = await asyncio.gather(*tasks)
            
            for name, stats in results:
                if stats:
                    team_stats[name] = stats
            
            print(f"[NCAAB PPG]   Processed {min(i+batch_size, len(teams_list))}/{len(teams_list)} teams ({len(team_stats)} with data)")
            await asyncio.sleep(0.5)  # Rate limiting
    
    print(f"[NCAAB PPG] Got Last 3 PPG for {len(team_stats)} teams")
    
    # Build lookup
    last3_values = {name: stats['last3_avg'] for name, stats in team_stats.items()}
    sorted_teams = sorted(last3_values.items(), key=lambda x: x[1], reverse=True)
    last3_ranks = {name: rank for rank, (name, _) in enumerate(sorted_teams, 1)}
    
    # Fuzzy match function
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
    
    def get_dot(rank):
        if rank is None: return '⚪'
        if rank <= 50: return '🟢'
        if rank <= 100: return '🔵'
        if rank <= 150: return '🟡'
        return '🔴'
    
    # Update games
    updated_games = []
    updated_count = 0
    
    for i, game in enumerate(existing_games, 1):
        away = game.get('away_team', '')
        home = game.get('home_team', '')
        
        away_ppg = find_value(away, last3_values)
        home_ppg = find_value(home, last3_values)
        away_rank = find_value(away, last3_ranks)
        home_rank = find_value(home, last3_ranks)
        
        combined = round(away_ppg + home_ppg, 1) if away_ppg and home_ppg else None
        if combined:
            updated_count += 1
        
        line = game.get('total') or game.get('opening_line')
        edge = round(combined - float(line), 1) if combined and line else None
        
        rec = ''
        if edge is not None:
            if edge >= 9: rec = 'OVER'
            elif edge <= -9: rec = 'UNDER'
        
        updated_game = {
            **game,
            'game_num': i,
            'away_last3_value': away_ppg,
            'away_last3_rank': away_rank,
            'away_ppg_value': away_ppg,
            'away_ppg_rank': away_rank,
            'home_last3_value': home_ppg,
            'home_last3_rank': home_rank,
            'home_ppg_value': home_ppg,
            'home_ppg_rank': home_rank,
            'combined_ppg': combined,
            'edge': edge,
            'recommendation': rec,
            'away_dots': get_dot(away_rank) + get_dot(away_rank),
            'home_dots': get_dot(home_rank) + get_dot(home_rank)
        }
        updated_games.append(updated_game)
    
    # Save to database
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
    
    print(f"[NCAAB PPG] DONE! Updated {updated_count}/{len(updated_games)} games")
    print(f"[NCAAB PPG] Plays preserved: {len(existing_plays)}")

if __name__ == "__main__":
    asyncio.run(main())
