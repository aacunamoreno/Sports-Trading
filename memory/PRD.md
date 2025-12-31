# BetBot - Automated Betting Analysis System

## Original Problem Statement
Create a system that can automatically log into accounts on the betting website `plays888.co`, scrape game data, place wagers based on specific scenarios, and track the results of both betting recommendations (edges) and the user's actual bets.

## User Accounts
- **ENANO Account:** `jac075`, Password: `acuna2025!`
- **TIPSTER Account:** `jac083`, Password: `acuna2025!`

## Core Requirements

### 1. 8pm Job (DONE)
Scrape and analyze tomorrow's opening lines for NBA, NHL, and NCAAB.
- Uses PPG (Points Per Game) rankings for NBA/NCAAB
- Uses GPG (Goals Per Game) rankings for NHL
- Status: **COMPLETED** (with data integrity workarounds)

### 2. Today Workflow (IN PROGRESS)
After 5am Arizona time, switch to using `plays888.co` for live odds.
- UI shows both opening and live lines
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
- **NBA: COMPLETED** (Dec 31, 2025)
- **NHL: COMPLETED** (Dec 31, 2025) - Supports both OT Included and Regulation Time bets
- **NCAAB: COMPLETED** (Dec 31, 2025) - Supports both TOTAL and SPREAD bets

### 6. NCAAB Spread Bet Highlighting (NOT STARTED)
Display spread bets with purple highlighting in UI.

### 7. Excel Export (BROKEN)
"Export Excel" button needs fixing.

## Known Issues

### Issue 1: Stat Scrapers Unreliable (P0)
- `teamrankings.com` returns 403 Forbidden
- `statmuse.com` returns 403 Forbidden
- **Workaround:** Hardcoded/locked PPG and GPG values

### Issue 2: NCAAB Spread Bets UI (P1)
- Single-team spread bets can't be matched to games
- Purple highlighting not implemented

### Issue 3: server.py Monolith (P2)
- 9,600+ lines in single file
- Needs modular refactoring

### Issue 4: Excel Export Broken (P2)
- Download doesn't trigger properly

## Architecture

```
/app/
├── backend/
│   ├── server.py             # Main backend (monolith)
│   ├── update_ncaab_ppg.py   # NCAAB PPG scraper
│   └── requirements.txt
├── frontend/
│   └── src/pages/
│       └── Opportunities.jsx # Main analysis UI
└── memory/
    └── PRD.md               # This file
```

## Key API Endpoints
- `GET /api/opportunities?league={NBA|NHL|NCAAB}&day={today|yesterday|tomorrow}`
- `POST /api/opportunities/ncaab/update-ppg` - Update NCAAB Last 3 PPG
- `POST /api/scores/{league}/update` - Update final scores
- `POST /api/bets/nba/update-results` - Update NBA bet results from History
- `POST /api/bets/nhl/update-results` - Update NHL bet results from History
- `POST /api/bets/ncaab/update-results` - Update NCAAB bet results from History

## Database Collections
- `nba_opportunities`, `nhl_opportunities`, `ncaab_opportunities`
  - Games with analysis, lines, scores, bet tracking
- `connections` - Account credentials (encrypted)
- `daily_compilations` - Telegram message tracking

## What's Been Implemented (Recent)

### Dec 31, 2025
- **NBA Bet Results Feature COMPLETED**
  - Fixed History page parser to correctly extract bet data
  - Parser now looks forward from NBA marker to find results AFTER team names
  - Correctly identifies WIN/LOSE for each bet
  - UI displays 💰 icon, bet line, and HIT/MISS status
  - "My Bets: X-Y" counter in header

- **NHL Bet Results Feature COMPLETED**
  - Extended bet results to NHL with support for both bet types:
    - Standard NHL bets (OT Included)
    - Regulation Time Only bets (marked as "SOC" sport in plays888)
  - Handles team name variations and REG.TIME suffixes
  - Found and matched 6 bets for Dec 29 (4-2 record)
  - UI displays bet tracking same as NBA

- **NCAAB Bet Results Feature COMPLETED**
  - Extended bet results to NCAAB (College Basketball)
  - Supports both bet types:
    - TOTAL bets (over/under) - requires both team names
    - SPREAD bets (single team with point spread)
  - College team name matching with fuzzy word overlap
  - Found and matched 16 bets for Dec 29 (7-9 record: 9 totals, 7 spreads)
  - UI displays bet tracking with spread indicator

### Dec 29-30, 2025
- NCAAB Last 3 PPG feature
- Yesterday scores feature for all leagues
- NHL GPG data integrity fix
- Bet data cleanup (removed duplicates)

## Upcoming Tasks (Priority Order)
1. (P0) Find permanent solution for blocked stat scrapers
2. (P1) Fix NCAAB spread bets purple highlighting in UI
3. (P1) Fix Excel export button
4. (P2) Add automated daily jobs for score/bet updates

## Future/Backlog
- Refactor server.py into modular architecture
- Build UI for custom betting rules
- Residential proxies or scraping API for blocked sources
