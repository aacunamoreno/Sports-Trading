# Betting Analysis System - Product Requirements Document

## Original Problem Statement
Build an automated betting analysis system for the website `plays888.co`. The system:
- Scrapes game data and consensus data
- Calculates betting edges
- Tracks user bets across two accounts: "TIPSTER" (jac083) and "ENANO" (jac075)
- Provides Telegram notifications with a real-time dashboard of all placed bets
- ENANO account displays a comparison view against TIPSTER to help copy bets

## Architecture
```
/app/
├── backend/
│   ├── .env
│   ├── requirements.txt
│   └── server.py             # Monolithic FastAPI backend
└── frontend/
    └── src/
        └── pages/
            └── Opportunities.jsx
```

## Key Technical Components
- **Playwright & BeautifulSoup**: Web scraping
- **APScheduler**: Scheduled job execution (7 AM - 11 PM Arizona time)
- **python-telegram-bot**: Telegram notifications
- **MongoDB**: Data persistence (test_database)

## Credentials
- TIPSTER: `jac083` / `acuna2025!`
- ENANO: `jac075` / `acuna2025!`

## Key Collections
- `daily_compilations`: Daily bet cache for Telegram messages
- `connections`: Account credentials and Telegram message IDs
- `bet_history`: Persistent log of all scraped bets (source of truth)

---

## What's Been Implemented

### 2026-01-20/21: Country/League Fix
- Fixed Python variable scoping error (`wager_short`, `to_win_short`, `game_short`, `bet_type_short`)
- Added country update logic for existing compilation bets
- Added country extraction to settled bets scraper
- Country/league now displays correctly in Telegram (NCAAB, NHL, Soccer, Tennis/AO, etc.)

### Previous Session Work
- Telegram notification system (5-minute intervals, 7AM-11PM Arizona)
- TIPSTER view: detailed bet list sorted by time
- ENANO view: comparison view against TIPSTER (loose matching - any bet on same game)
- Open/settled bet sync logic
- Deduplication in daily_compilations

---

## P0 - Critical (Done)
- ✅ Country/league information in Telegram messages

## P1 - High Priority
- Refactor data scraping/sync pipeline (idempotent sync function)
- Fix OVER/UNDER bet type identification
- Refactor `server.py` monolith

## P2 - Medium Priority  
- NCAAB records verification
- Fix "Regulation Time" bet parsing
- Fix betting line format edge cases

## P3 - Backlog
- Backfill country data for historical bets
- Custom betting rules UI
