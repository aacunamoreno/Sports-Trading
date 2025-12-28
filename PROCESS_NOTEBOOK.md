# Betting Bot Process Notebook

## Reference: Starting Point 7:50pm

---

## Daily Automated Processes

### #1 - 8:00 PM: Scrape Tomorrow's Games (Opening Lines)
**Source:** ScoresAndOdds.com
**Action:** Scrape tomorrow's games for all leagues (NBA, NHL, NFL)
- These are the **opening lines** for each game
- After initial scrape, track line movements until game starts
- Store opening lines in `opening_lines` collection

**Leagues:**
- NBA: `https://www.scoresandodds.com/nba?date={tomorrow}`
- NHL: `https://www.scoresandodds.com/nhl?date={tomorrow}`
- NFL: `https://www.scoresandodds.com/nfl`

---

### #2 - After Scraping: Fill PPG Data & Dots
**Formula:** 
```
GPG Avg = (Team1 Season PPG + Team2 Season PPG + Team1 L3 PPG + Team2 L3 PPG) / 2
Edge = GPG Avg - Line
```

**PPG Source:** TeamRankings.com
- NBA: `https://www.teamrankings.com/nba/stat/points-per-game`
- NHL: `https://www.teamrankings.com/nhl/stat/points-per-game`
- NFL: `https://www.teamrankings.com/nfl/stat/points-per-game`

**4 Dots System:**
- 🟢 Green: Rank 1-8 (Top tier)
- 🔵 Blue: Rank 9-16 (Upper middle)
- 🟡 Yellow: Rank 17-24 (Lower middle)
- 🔴 Red: Rank 25-32 (Bottom tier)

Display dots for:
1. Away Team Season Rank
2. Away Team Last 3 Rank
3. Home Team Season Rank
4. Home Team Last 3 Rank

---

### #3 - 5:00 AM: Switch to Plays888 Live Lines
**Trigger:** First agent interaction after 5am
**Source:** Plays888.co (Live betting lines)
**Action:** 
- Stop using ScoresAndOdds for today's games
- Start scraping live lines from Plays888
- Update all "today" games with Plays888 lines

---

### #4 - 5:00 AM: Get Yesterday's Scores
**Source:** ScoresAndOdds.com
**Action:** Scrape final scores for all yesterday's games
- NBA: `https://www.scoresandodds.com/nba?date={yesterday}`
- NHL: `https://www.scoresandodds.com/nhl?date={yesterday}`
- NFL: `https://www.scoresandodds.com/nfl` (check results)

**Update:**
- `final_score` field for each game
- Calculate `diff` (Final - Line)
- Determine OVER/UNDER result

---

### #5 - 5:00 AM: Get Bet Results from History
**Source:** Plays888.co → History page
**Action:** 
- Login to Plays888 with credentials
- Navigate to History section
- Extract all settled bets with results (won/lost)
- Match bets to games and update `user_bet_hit` field

**Credentials:**
- Account 1: jac075 / acuna2025! (ENANO - Main bets)
- Account 2: jac083 / acuna2025! (TIPSTER - Copy bets)

---

### #6 - 5:00 AM: Update Records
**Action:** Calculate and update all records

**Betting Record:** (Only ENANO account bets > $2k)
- Count wins and losses from settled bets
- Update `compound_records` collection

**Edge Record:** (When edge recommendation matched result)
- If Edge recommended OVER and game went OVER = HIT
- If Edge recommended UNDER and game went UNDER = HIT
- Otherwise = MISS
- Update `edge_records` collection

---

## Edge Thresholds by League

| League | Strong Play Threshold |
|--------|----------------------|
| NBA    | Edge ≥ 5 points      |
| NHL    | Edge ≥ 0.5 goals     |
| NFL    | Edge ≥ 7 points      |

---

## Data Sources Summary

| Time | Source | Data |
|------|--------|------|
| 8pm-5am | ScoresAndOdds | Tomorrow's lines, Opening lines |
| 5am onwards | Plays888 | Today's live lines |
| 5am | ScoresAndOdds | Yesterday's final scores |
| 5am | Plays888 History | Bet results (won/lost) |
| Always | TeamRankings | PPG Season & Last 3 |

---

## Database Collections

- `nba_opportunities` - NBA games and analysis
- `nhl_opportunities` - NHL games and analysis  
- `nfl_opportunities` - NFL games and analysis
- `opening_lines` - First scraped line for each game
- `open_bets` - Current active bets
- `bet_history` - Historical bet results
- `compound_records` - Betting win/loss records by league
- `edge_records` - Edge recommendation accuracy by league
- `daily_compilations` - Daily bet summaries

---

## Current Records

| League | Betting Record | Edge Record |
|--------|---------------|-------------|
| NBA    | 8-6           | TBD         |
| NHL    | 6-5           | TBD         |
| NFL    | 0-0           | TBD         |

---

*Last Updated: December 27, 2025*
