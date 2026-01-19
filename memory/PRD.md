# BetScout - Automated Betting Analysis System

## Original Problem Statement
Build an automated betting analysis system for `plays888.co` that scrapes game data (lines, scores, spreads, moneylines), betting consensus data, calculates betting edges, tracks user bets, and displays all information in a unified dashboard.

## Core Features Implemented

### Data Scraping & Analysis
- Live lines scraping from CBS Sports (NBA, NHL, NCAAB, NFL)
- Public betting consensus scraping from Covers.com
- User bet tracking from plays888.co
- Edge calculation based on PPG (Points Per Game) averages
- Automated bet monitoring with background loops

### Dashboard Features
- Multi-league support (NBA, NHL, NCAAB, NFL)
- Today/Yesterday/Tomorrow views with calendar picker
- NFL Week Selector (Weeks 1-18) for historical data
- Edge Record, Betting Record, Ranking PPG, Public Record tracking
- Compound Public Record Modal with percentage-range breakdown
- Real-time line updates via "Refresh Lines & Bets" button

### Data Management
- Full NFL historical data backfill (18 weeks)
- Manual record update functionality
- Excel file import for data corrections
- MongoDB storage for all leagues

## What's Been Implemented (Latest First)

### January 19, 2026 (Session 3)
- **Bug Fix - ENANO Telegram Summary**: Fixed two issues with the ENANO (jac075) Telegram notification:
  1. Removed the "short" summary message - ENANO now only receives the detailed comparison view
  2. Fixed "Missed" count calculation - now correctly counts TIPSTER bets that ENANO didn't copy where either:
     - The game has a final result (won/lost/push)
     - The game has already started (game time passed)
- **Refactor - send_all_compilations API**: Updated the manual `/api/telegram/send-compilations` endpoint to send ENANO comparison view + TIPSTER detailed view only (2 messages instead of 3)

### January 10-11, 2026 (Session 2)
- **Bug Fix - Completed Games Preserved**: Fixed critical issue where completed games (with final_score) were disappearing when clicking "Refresh Lines & Bets". Now preserves all bet data (bet_type, bet_line, user_bet_hit, result) for finished games.
- **Bug Fix - RBL Sport Parsing**: Fixed issue where bets marked as "RBL" (special plays888 line type) were not being matched to NBA games. Added logic to detect "Basketball / NBA" in bet descriptions.
- **Bug Fix - Slash Format Bet Parsing**: Fixed bet parser to handle new plays888 format with slash separators (e.g., "Cleveland Cavaliers vs Minnesota Timberwolves / Game / Total / Under 242.5")
- **Manual Fix - Minnesota vs Cleveland**: Manually added the UNDER 242.5 bet that was lost due to parsing issues.

### January 10, 2026 (Session 1)
- **Public Consensus Scraping on Refresh**: Integrated `scrape_covers_consensus` into the "Refresh Lines & Bets" endpoint so clicking the button now scrapes and updates public betting percentages from Covers.com
- **UI Update**: Consensus percentages now display for today's games (not just historical), showing in red next to team rankings

### Previous Session
- Full NFL Data Overhaul (all 18 weeks)
- NFL Week Selector component
- Compound Public Record Modal
- Spread display bug fix (home favorites)
- Multiple data corrections per user

## Architecture

### Backend: `/app/backend/server.py`
- Monolithic FastAPI application
- Playwright for web scraping
- APScheduler for scheduled jobs
- MongoDB via Motor (async)

### Frontend: `/app/frontend/src/pages/Opportunities.jsx`
- Single large React component
- Uses Shadcn/UI components

### Database: MongoDB (test_database)
- Collections: `nba_opportunities`, `nhl_opportunities`, `ncaab_opportunities`, `nfl_opportunities`
- Records: `compound_records`, `ranking_ppg_records`

## Key API Endpoints
- `POST /api/opportunities/refresh-lines` - Refresh lines, bets, AND consensus data (preserves completed games)
- `POST /api/bets/nba/update-results` - Update NBA bet results from plays888 history
- `POST /api/bets/nhl/update-results` - Update NHL bet results
- `POST /api/bets/ncaab/update-results` - Update NCAAB bet results
- `GET /api/records/public-compound/{league}` - Compound public record data
- `GET /api/opportunities/nfl/{week}` - NFL games by week
- `GET /api/records/summary` - All record summaries

## Known Issues (P1)

### Issue 1: plays888.co OVER/UNDER Scraper Bug
- The scraper incorrectly identifies bet types (OVER vs UNDER) in some formats
- Status: NOT STARTED
- Impact: Incorrect bet tracking and grading

### Issue 2: plays888.co "Regulation Time" Bug
- Bets marked "REG.TIME" not handled correctly
- Affects NHL games especially (PUSH if game goes to overtime)
- Status: NOT STARTED

## Resolved Issues

### ✅ ENANO Telegram Summary Bug (Fixed Jan 19, 2026)
- Issue: ENANO was receiving an extra "short" summary message and "Missed" count was always 0
- Fix: Removed short message logic for ENANO, fixed missed count to include both completed and started games

## Technical Debt (P1)

### server.py Refactoring
- File is extremely large and monolithic
- Needs splitting into: `routes/`, `services/`, `scrapers/`
- Status: NOT STARTED

### Opportunities.jsx Refactoring
- Component is over 2000 lines
- Modal, week selector, data display should be separate components
- Status: NOT STARTED

## Upcoming Tasks
- (P2) NCAAB records verification with user guidance
- (P1) Custom betting rules UI

## Credentials
- plays888.co Betting: `jac075` / `acuna2025!`
- plays888.co Lines: `jac083` / `acuna2025!`

## 3rd Party Integrations
- Playwright (web scraping)
- BeautifulSoup (HTML parsing)
- APScheduler (scheduled jobs)
- openpyxl (Excel parsing)
- python-telegram-bot (Telegram notifications)

## Telegram Notification System
- **Schedule**: Every 5 minutes from 7 AM to 10 PM Arizona time
- **TIPSTER (jac083)**: Detailed list of all bets sorted by completion status, date, and time
- **ENANO (jac075)**: Comparison view against TIPSTER bets with indicators:
  - 🔵 = Bet successfully copied
  - 🟡 = Pending (can still place)
  - 🔴 = Missed (game started/completed, not bet)
- **Summary**: Shows Copied/Total, Missed count, Pending count
