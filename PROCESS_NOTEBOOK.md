# 🎯 BetBot Process Notebook
**Last Updated:** December 27, 2025  
**Leagues:** NBA | NHL | NFL

---

## 📊 DATA SOURCES

| Data Type | Source | URL |
|-----------|--------|-----|
| **NFL PPG & Rankings** | TeamRankings | https://www.teamrankings.com/nfl/stat/points-per-game |
| **NBA PPG & Rankings** | TeamRankings | https://www.teamrankings.com/nba/stat/points-per-game |
| **NHL GPG & Rankings (Season)** | ESPN | https://www.espn.com/nhl/stats/team |
| **NHL GPG & Rankings (Last 3)** | StatMuse | https://www.statmuse.com/nhl/ask/nhl-teams-with-most-goals-scored-last-3-games |
| **Open Bets & History** | Plays888 | https://plays888.co |
| **Game Schedules & Results** | ScoresAndOdds | https://scoresandodds.com |

---

## 🔢 FORMULAS & CALCULATIONS

### PPG/GPG Average Formula
```
Combined PPG = (Team1 Season PPG + Team2 Season PPG + Team1 L3 PPG + Team2 L3 PPG) / 2
```

### Edge Calculation
```
Edge = Combined PPG - Betting Line
```

### Edge Thresholds (for Recommendations)
| League | Threshold | OVER if | UNDER if |
|--------|-----------|---------|----------|
| **NBA** | ±5 points | Edge ≥ +5 | Edge ≤ -5 |
| **NHL** | ±0.5 goals | Edge ≥ +0.5 | Edge ≤ -0.5 |
| **NFL** | ±7 points | Edge ≥ +7 | Edge ≤ -7 |

### 4-Dot Color System (PPG Rankings)
| Dot Color | Rank Range | Meaning |
|-----------|------------|---------|
| 🟢 Green | 1-8 | Top tier (high-scoring) |
| 🔵 Blue | 9-16 | Upper middle |
| 🟡 Yellow | 17-24 | Lower middle |
| 🔴 Red | 25-32 | Bottom tier (low-scoring) |

**Dot Order:** `[Away Season] [Away L3] [Home Season] [Home L3]`

---

## ⏰ SCHEDULED PROCESSES

### 🌙 EVENING PROCESS (8:00 PM Arizona)

#### #1 - Scrape Tomorrow's Opening Lines ✅
**Time:** 8:00 PM Arizona  
**Source:** ScoresAndOdds.com  
**Actions:**
- Scrape tomorrow's games for NBA, NHL, NFL
- Store as **opening lines** (these are the baseline for tracking line movement)
- **NFL Exception:** NFL is weekly, so:
  - If next week's games already exist → Skip scraping, just update lines if changed
  - If new week → Scrape all games for that week
- After this, track line changes until game starts

#### #2 - Populate PPG Data & 4-Dot Analysis ✅
**Time:** Immediately after #1  
**Sources:** TeamRankings (NBA/NFL), ESPN + StatMuse (NHL)  
**Actions:**
- For each game scraped in #1:
  - Fetch Season PPG rankings and values for both teams
  - Fetch Last 3 Games PPG rankings and values for both teams
  - Calculate Combined PPG using formula
  - Calculate Edge (PPG - Line)
  - Generate 4 dots with correct colors based on rankings
  - Store recommendation (OVER/UNDER/None) based on edge threshold

---

### 🌅 MORNING PROCESS (5:00 AM Arizona)
*Note: "5am" means first time agent is activated after 5am*

#### #3 - Switch Data Source to Plays888
**Time:** 5:00 AM Arizona (or first activation after)  
**Source:** Plays888.co  
**Actions:**
- Change TODAY's games data source from ScoresAndOdds → Plays888
- Plays888 has live/current lines for today's games
- Keep ScoresAndOdds for yesterday's results and tomorrow's opening lines

#### #4 - Get Yesterday's Final Scores
**Time:** 5:00 AM Arizona  
**Source:** ScoresAndOdds.com  
**Actions:**
- Scrape final scores for all games from yesterday (NBA, NHL, NFL)
- Update yesterday's games with:
  - `final_score`: Total points/goals scored
  - `result`: OVER or UNDER (compare final_score vs line)
  - `result_hit`: true/false (did our recommendation hit?)

#### #5 - Get Bet Results from History
**Time:** 5:00 AM Arizona  
**Source:** Plays888.co → "History" tab  
**Actions:**
- Login to Plays888 (both ENANO jac075 and TIPSTER jac083)
- Go to "History" section
- Scrape all settled bets from yesterday
- For each bet, record:
  - Game details (teams, sport)
  - Bet type (OVER/UNDER)
  - Line at bet time
  - Risk amount
  - Win/Loss result
  - Payout (if won)

#### #6 - Update Betting & Edge Records
**Time:** 5:00 AM Arizona  
**Database:** compound_records collection  
**Actions:**
- **Betting Record:** Count of actual bets placed (from ENANO account only, $2k+ bets)
  - Summarize from 12/23/25 onwards
  - Format: W-L (e.g., "8-6")
- **Edge Record:** Count of edge recommendations that hit
  - Summarize from 12/23/25 onwards
  - Format: W-L (e.g., "12-8")
- Update for each league separately (NBA, NHL, NFL)

---

### 🔄 ON-DEMAND PROCESSES (User Actions)

#### #7 - Refresh Data Button
**Trigger:** User clicks "Refresh Data" button  
**Sources:** Plays888.co  
**Actions:**
1. **Get Live Odds:**
   - Fetch current lines from Plays888 for all games
   - Compare with opening line (from #1) to show line movement
   - If line no longer available on Plays888 → Keep last known line
   
2. **Check for New Bets:**
   - Go to "Open Bets" section in Plays888
   - Compare with stored open bets
   - If new bet found → Add to open_bets collection
   - Send Telegram notification for new bets

3. **Update Display:**
   - Show current line
   - Show opening line (in gray)
   - Show line movement (e.g., "223 → 225 ⬆️")

#### #8 - TODAY'S PLAYS Display
**Location:** Top of Opportunities page  
**Rule:** Show ALL active bets, regardless of game status  
**Display Logic:**
- Show bets even if game has started
- Show bets even if game has ended (until settled)
- Only remove from TODAY'S PLAYS when bet is settled (moved to History)
- Include:
  - Teams
  - Bet type (OVER/UNDER)
  - Line at bet time
  - Risk amount
  - Current game status (if available)

---

## 📋 PROCESS STATUS TRACKER

| # | Process | Status | Last Run | Notes |
|---|---------|--------|----------|-------|
| 1 | Scrape Tomorrow's Opening Lines | ✅ Ready | - | 8pm scheduled job |
| 2 | Populate PPG & 4-Dots | ✅ Ready | - | Runs after #1 |
| 3 | Switch to Plays888 (5am) | 🟡 Pending | - | Morning job |
| 4 | Get Yesterday's Scores | 🟡 Pending | - | Morning job |
| 5 | Get Bet Results from History | 🟡 Pending | - | Morning job |
| 6 | Update Records | 🟡 Pending | - | Morning job |
| 7 | Refresh Data Button | 🟡 Partial | - | Needs line movement tracking |
| 8 | TODAY'S PLAYS Display | 🟡 Partial | - | Needs to persist after game start |

---

## 🔑 ACCOUNTS & CREDENTIALS

### Plays888 Accounts
| Label | Username | Password | Purpose |
|-------|----------|----------|---------|
| **ENANO** | jac075 | acuna2025! | Main betting account ($2k+ bets) - counts for record |
| **TIPSTER** | jac083 | acuna2025! | Copy account ($1k bets) - does NOT count for record |

### Telegram Notifications
| Setting | Value |
|---------|-------|
| Bot Token | `8546689425:AAFvupveQxoY-eO8RunzOAiubeY0jSIFCto` |
| Group Chat ID | `-5058656467` |

---

## 📝 IMPORTANT NOTES

1. **Betting Record** = Only counts ENANO bets ($2k+), NOT TIPSTER copies
2. **Edge Record** = Tracks whether our PPG-based recommendations hit
3. **NFL is Weekly** = Don't re-scrape if week's games exist, just update lines
4. **Line Movement** = Opening line (8pm) vs Current line (Plays888)
5. **Record Start Date** = December 23, 2025

---

## 🛠️ API ENDPOINTS

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/process/8pm` | POST | Manually trigger 8pm process (#1 + #2) |
| `/api/process/status` | GET | Check status of tomorrow's data |
| `/api/opportunities/{league}` | GET | Get opportunities for league |
| `/api/opportunities/{league}/refresh` | POST | Refresh data for league |
