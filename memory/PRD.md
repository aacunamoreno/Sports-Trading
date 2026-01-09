# PRD - SportsTrading Betting Analysis System

## Original Problem Statement
Build an automated betting analysis system for `plays888.co` that:
- Scrapes game data (lines, scores, spreads, moneylines)
- Scrapes betting consensus data from multiple sources
- Calculates betting edges
- Tracks user bets
- Displays all information in a unified dashboard

## User Personas
- Sports bettor who wants data-driven insights
- Needs real-time and historical betting analysis

## Core Requirements
1. Multi-sport support (NBA, NHL, NCAAB, NFL)
2. Dynamic public record with adjustable consensus threshold (57%-70%)
3. Edge calculations based on line movements
4. Historical data tracking and backfill capability
5. Integration with plays888.co for bet tracking

---

## Changelog

### 2026-01-09
- **Added NFL Support:**
  - Parsed 261 NFL games from Excel file (corrected week offset)
  - Scraped scores from ESPN for 2025 NFL season
  - Added NFL to Public Record API endpoint
  - Updated frontend with NFL tab and league-specific settings
  - NFL Public Record: 50-119 at 57% threshold (29.6% win rate)

- **Fixed:** Public Record display showing 131-131 instead of correct 163-166 for NBA
  - Removed conflicting useEffect that overwrote dynamic threshold data

### Previous Session
- Historical NBA data backfill (Oct 21 - Dec 21, 2025)
- Dynamic Public Record threshold selector (57%-70%)
- NHL Line editing feature with automatic Edge recalculation
- Team name aliases for NCAAB
- Spread display fix for favored away teams

---

## P0 Issues (Critical)
1. **OVER/UNDER Scraper Bug** - `plays888.co` scraper misidentifies "o/u TOTAL..." format bets

## P1 Issues (High)
1. **Refactor server.py** - 15,000+ line monolith needs to be broken into modules
2. **Custom Betting Rules UI** - Allow users to create/manage rules

## P2 Issues (Medium)
1. **Regulation Time Bet Bug** - NHL bets with "REG.TIME" incorrectly result in PUSHes

---

## Architecture
```
/app/
├── backend/
│   ├── server.py (monolithic - needs refactoring)
│   └── requirements.txt
├── frontend/
│   └── src/pages/Opportunities.jsx (main UI)
└── memory/PRD.md
```

## Key API Endpoints
- `GET /api/records/public-by-threshold/{league}?threshold=57` - Dynamic public record
- `GET /api/opportunities/nfl?day=today` - NFL opportunities
- `POST /api/game/update-line` - Update game line

## Database Collections
- `nba_opportunities` - NBA game data
- `nhl_opportunities` - NHL game data  
- `ncaab_opportunities` - NCAAB game data
- `nfl_opportunities` - NFL game data (18 documents, 261 games)
