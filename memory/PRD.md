# BetBot - Automated Betting Analysis System

## Original Problem Statement
Create a system that can automatically log into accounts on the betting website `plays888.co`, scrape game data, place wagers based on specific scenarios, and track the results of both betting recommendations (edges) and the user's actual bets.

## User Accounts
- **ENANO Account:** `jac075`, Password: `acuna2025!`
- **TIPSTER Account:** `jac083`, Password: `acuna2025!`

## Core Requirements

### 1. 8pm Job - Scrape Tomorrow's Opening Lines (COMPLETED ✅)
Scrape and analyze tomorrow's opening lines for NBA, NHL, and NCAAB.
- **API Endpoint:** `POST /api/process/scrape-openers?target_date=YYYY-MM-DD`
- **Data Sources:** CBS Sports (primary for all leagues), ScoresAndOdds (fallback)
- **UI Button:** "Scrape Tomorrow (8pm Job)" - cyan colored button
- Status: **COMPLETED** (Dec 31, 2025)
  - NBA: 9 games scraped
  - NHL: 10 games scraped
  - NCAAB: 49 games scraped

### 2. Today Workflow (COMPLETED)
After 5am Arizona time, switch to using `plays888.co` for live odds.
- UI shows both opening and live lines
- "Refresh Lines" button for safe updates
- Status: **COMPLETED**

### 3. NCAAB Data Integrity (DONE)
Use Last 3 Games PPG average from `cbssports.com` for NCAAB analysis.
- "Update PPG (L3)" button added to UI
- Status: **COMPLETED** (Dec 29, 2025)

### 4. Results Tracking (DONE)
Scrape yesterday's final scores from `ScoresAndOdds.com` to mark edge recommendations as HIT/MISS.
- "Update Scores" button added to UI
- Status: **COMPLETED** (Dec 29, 2025)

### 5. Bet Tracking (COMPLETED)
Scrape user's bet results (Win/Loss) from `plays888.co` History page.
- Show 💰 icon for games with bets
- Display exact bet line
- Show outcome (HIT/MISS)
- Store `actual_bet_record` from History page to handle duplicate bets correctly
- **NBA: COMPLETED** (Dec 31, 2025)
- **NHL: COMPLETED** (Dec 31, 2025) - Supports both OT Included and Regulation Time bets
  - **Bet Highlighting Fix Applied** (Dec 31, 2025) - `plays` array now syncs with games
- **NCAAB: COMPLETED** (Dec 31, 2025) - Supports both TOTAL and SPREAD bets, counts duplicates correctly

### 6. NCAAB Spread Bet Highlighting (COMPLETED)
Display spread bets with purple highlighting in UI.
- 🎰 icon for spread bets (vs 💰 for total bets)
- Purple ring around row
- Purple background tint
- 📊 spread value indicator (vs 🎯 for total lines)
- Purple-styled result badges (SPREAD HIT / SPREAD MISS)
- Legend updated to explain spread bet styling
- **COMPLETED** (Dec 31, 2025)

### 7. Cumulative Records Feature (COMPLETED)
Calculate and display cumulative betting and edge records from 12/22/25.
- "Update Records" button in UI
- Status: **COMPLETED** (Dec 31, 2025)

### 8. Excel Export (BROKEN)
"Export Excel" button needs fixing.

## Known Issues

### Issue 1: Stat Scrapers Unreliable (P0)
- `teamrankings.com` returns 403 Forbidden
- `statmuse.com` returns 403 Forbidden
- `scoresandodds.com` returns 403 Forbidden
- **Solution Implemented:** CBS Sports scrapers as primary source for all leagues
- **Pending:** Process #2 - Manual input UI for PPG/GPG stats

### Issue 2: server.py Monolith (P2)
- 11,000+ lines in single file
- Needs modular refactoring

### Issue 3: Excel Export Broken (P2)
- Download doesn't trigger properly

## Architecture

```
/app/
├── backend/
│   ├── server.py             # Main backend (monolith, 11,000+ lines)
│   ├── update_ncaab_ppg.py   # NCAAB PPG scraper
│   └── requirements.txt
├── frontend/
│   └── src/pages/
│       └── Opportunities.jsx # Main analysis UI
└── memory/
    └── PRD.md               # This file
```

## Key API Endpoints
- `GET /api/opportunities?league={NBA|NHL|NCAAB}&day={today|yesterday|tomorrow|YYYY-MM-DD}`
- `GET /api/opportunities/nhl?day={today|yesterday|tomorrow|YYYY-MM-DD}`
- `GET /api/opportunities/ncaab?day={today|yesterday|tomorrow|YYYY-MM-DD}`
- `POST /api/process/scrape-openers?target_date=YYYY-MM-DD` - 8pm Job to scrape opening lines
- `POST /api/process/update-records?start_date=YYYY-MM-DD` - Recalculate cumulative records
- `POST /api/opportunities/refresh-lines` - Refresh live lines from plays888.co
- `POST /api/opportunities/ncaab/update-ppg` - Update NCAAB Last 3 PPG
- `POST /api/scores/{league}/update` - Update final scores
- `POST /api/bets/{league}/update-results` - Update bet results from History

## Database Collections
- `nba_opportunities`, `nhl_opportunities`, `ncaab_opportunities`
  - Games with analysis, lines, scores, bet tracking
- `opening_lines` - Stores opening lines for tracking
- `compound_records`, `edge_records` - Cumulative record tracking
- `connections` - Account credentials (encrypted)
- `daily_compilations` - Telegram message tracking

## What's Been Implemented (Recent)

### Dec 31, 2025 - History Bets Integration COMPLETED
- **Feature Added:** Refresh now scrapes both Open Bets AND today's History (settled) bets
- **New Function:** `scrape_todays_history_bets()` - parses History page for today's settled bets
- **Bets Now Tracking:**
  - Open bets (active/pending)
  - History bets (already settled - WIN/LOSE)
- **Team Name Normalization Enhanced:**
  - "N. Illinois" ↔ "NORTHERN ILLINOIS"
  - "FAU" ↔ "FLORIDA ATLANTIC"
  - "Loyola Chi." ↔ "LOYOLA CHICAGO"
  - "Boston U." ↔ "BOSTON UNIVERSITY"
- **Verification:** 28 total NCAAB bets now tracking correctly including:
  - Wofford x2 (2 identical spread bets)
  - Lehigh 2 bets (total + spread)
  - Lamar 2 bets (total + spread)
  - Duke 2 bets (total + spread)
  - Memphis 2 bets (total + spread)
  - St. Joseph's 2 bets (total + spread)

### Dec 31, 2025 - Multiple Bet Types Per Game Fix COMPLETED
- **Bug Fixed:** Games with both spread AND total bets were only showing one bet type
- **Root Cause:** 
  1. Bet matching logic was overwriting previous bets instead of accumulating
  2. MEMPHIS spread bets were incorrectly classified as NBA (due to Memphis Grizzlies match)
  3. Frontend wasn't displaying multiple bet types per game
- **Fixes Applied:**
  1. Backend: Reset bet tracking arrays on each refresh to prevent accumulation across refreshes
  2. Backend: Fixed sport detection to prioritize context (CBB label) over team name matching
  3. Backend: Track `bet_types[]` and `bet_count` per game to support multiple bets
  4. Frontend: Updated Bet column to display multiple bet types vertically with correct colors:
     - Green for OVER, Orange for UNDER, Purple for SPREAD bets
     - Shows "x2" notation for duplicate bets
- **Files Modified:** `/app/backend/server.py`, `/app/frontend/src/pages/Opportunities.jsx`
- **Verification:**
  - Duke row shows: ⬇️ UNDER x2 + 📊 DUKE -25.5 + 📊 DUKE -26
  - Memphis row shows: ⬇️ UNDER x2 + 📊 MEMPHIS -9.5 + 📊 MEMPHIS -10

### Dec 31, 2025 - NHL Bet Highlighting Fix COMPLETED
- **Bug Fixed:** NHL bets were not being highlighted in the UI table
- **Root Cause 1:** The `plays` array wasn't being updated when bets were matched to games
- **Root Cause 2:** The table row highlighting was too subtle (50% opacity)
- **Root Cause 3:** The "Bet" column wasn't showing bet type for games with bets
- **Fixes Applied:** 
  1. Updated `/api/opportunities/refresh-lines` endpoint to sync `plays` array with games that have bets
  2. Made table row highlighting more prominent: `ring-2 ring-yellow-500 bg-yellow-500/10` (full opacity ring + 10% yellow background)
  3. Added bet type display in the "Bet" column: shows "⬆️ OVER" or "⬇️ UNDER" in green/orange for games with active bets
- **Files Modified:** `/app/backend/server.py`, `/app/frontend/src/pages/Opportunities.jsx`
- **Verification:** All 3 NHL bets now display correctly with:
  - Yellow highlighting on table rows
  - 💰 icon in the # column
  - "⬆️ OVER" in green in the Bet column

### Dec 31, 2025 - Process #1 (8pm Job) COMPLETED
- **CBS Sports Scrapers Implemented**
  - `scrape_cbssports_nba()` - Scrapes NBA games from CBS Sports
  - `scrape_cbssports_nhl()` - Scrapes NHL games from CBS Sports
  - `scrape_cbssports_ncaab()` - Already existed, verified working
  - All include team name normalization
- **New API Endpoint:** `/api/process/scrape-openers`
  - Orchestrates scraping for all three leagues
  - Stores games with opening lines in opportunities collections
  - Also stores in `opening_lines` collection for tracking
  - Uses CBS Sports as primary (scoresandodds.com blocked with 403)
- **New UI Button:** "Scrape Tomorrow (8pm Job)"
  - Cyan colored button in the control bar
  - Shows toast notification during scraping
  - Auto-refreshes if viewing tomorrow's data
- **Results for Dec 31, 2025:**
  - NBA: 9 games (Golden State @ Brooklyn, Minnesota @ Atlanta, etc.)
  - NHL: 10 games (NY Rangers @ Washington, Toronto @ Vegas, etc.)
  - NCAAB: 49 games (Army @ Lehigh, Lamar @ East Texas A&M, etc.)

### Dec 31, 2025 - Previous Session
- **Records Update Feature (#6) COMPLETED**
- **NCAAB Bet Record Fix** - Correct duplicate counting
- **NBA/NHL/NCAAB Bet Results Feature COMPLETED**

## Upcoming Tasks (Priority Order)
1. (P0) **Process #2:** Build manual input UI for PPG/GPG stats (blocked scrapers workaround)
2. (P1) Fix Excel export button
3. (P1) Implement remaining daily processes (#3-7)
4. (P2) Fix NCAAB Spread Bet matching logic

## Future/Backlog
- Refactor server.py into modular architecture
- Build UI for custom betting rules
- Residential proxies or scraping API for blocked sources
