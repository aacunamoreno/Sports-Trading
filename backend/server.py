from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
import random
from datetime import datetime, timezone, timedelta
from cryptography.fernet import Fernet
import base64
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import httpx
from telegram import Bot
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Encryption key for storing credentials
encryption_key = os.environ.get('ENCRYPTION_KEY')
if not encryption_key:
    encryption_key = Fernet.generate_key().decode()
    print(f"Generated new encryption key. Add to .env: ENCRYPTION_KEY={encryption_key}")
cipher_suite = Fernet(encryption_key.encode())

# Telegram Bot setup (optional - will be configured later)
telegram_bot = None
telegram_chat_id = None

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Telegram after logger is set up
async def init_telegram_from_db():
    """Initialize Telegram bot from database configuration"""
    global telegram_bot, telegram_chat_id
    try:
        # Try to load from database first
        config = await db.telegram_config.find_one({}, {"_id": 0})
        if config:
            telegram_bot = Bot(token=config["bot_token"])
            telegram_chat_id = int(config["chat_id"])
            logger.info(f"Telegram initialized from database (Chat ID: {telegram_chat_id})")
            return
    except Exception as e:
        logger.error(f"Error loading Telegram from database: {e}")
    
    # Fall back to environment variables
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if token and chat_id:
        telegram_bot = Bot(token=token)
        telegram_chat_id = int(chat_id)
        logger.info("Telegram initialized from environment variables")
    else:
        logger.info("Telegram not configured (optional feature)")

# Startup event to initialize Telegram and auto-start monitoring
@app.on_event("startup")
async def startup_event():
    await init_telegram_from_db()
    await auto_start_monitoring()
    schedule_daily_summary()
    await startup_recovery()  # Check if we missed anything overnight

async def delete_message_later(bot, chat_id, message_id, delay_minutes=30):
    """Delete a Telegram message after a delay - used for status notifications"""
    try:
        await asyncio.sleep(delay_minutes * 60)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Auto-deleted status message {message_id} after {delay_minutes} min")
    except Exception as e:
        logger.debug(f"Could not auto-delete message {message_id}: {e}")

def schedule_daily_summary():
    """Schedule the daily summary to run at 11 PM Arizona time"""
    global scheduler
    
    # Arizona is UTC-7 (no daylight saving)
    # 11 PM Arizona = 6 AM UTC next day (23:00 - 7 = 16:00? No wait...)
    # Actually: Arizona UTC-7, so 11 PM Arizona = 11 PM + 7 hours = 6 AM UTC next day
    # Let's use cron with timezone
    
    try:
        # Activity summary at 10:59 PM Arizona
        scheduler.add_job(
            send_activity_summary,
            trigger=CronTrigger(hour=22, minute=45, timezone='America/Phoenix'),  # 10:45 PM Arizona
            id='activity_summary',
            replace_existing=True
        )
        logger.info("Activity summary scheduled for 10:45 PM Arizona time")
        
        # Betting summary at 11:00 PM Arizona
        scheduler.add_job(
            send_daily_summary,
            trigger=CronTrigger(hour=22, minute=45, timezone='America/Phoenix'),  # 10:45 PM Arizona
            id='daily_summary',
            replace_existing=True
        )
        logger.info("Daily summary scheduled for 10:45 PM Arizona time")
        
        # Daily cleanup at 9:00 AM Arizona
        scheduler.add_job(
            daily_cleanup,
            trigger=CronTrigger(hour=9, minute=0, timezone='America/Phoenix'),  # 9 AM Arizona
            id='daily_cleanup',
            replace_existing=True
        )
        logger.info("Daily cleanup scheduled for 9:00 AM Arizona time")
    except Exception as e:
        logger.error(f"Error scheduling daily tasks: {str(e)}")

async def auto_start_monitoring():
    """Auto-start bet monitoring if it was previously enabled"""
    global monitoring_enabled
    from zoneinfo import ZoneInfo
    arizona_tz = ZoneInfo('America/Phoenix')
    
    try:
        # Check if there's an active connection
        conn = await db.connections.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
        if conn and conn.get("is_connected"):
            # Check if monitoring was previously enabled (stored in DB)
            monitor_config = await db.monitor_config.find_one({}, {"_id": 0})
            if monitor_config and monitor_config.get("auto_start", True):
                monitoring_enabled = True
                
                # Check if we missed a scheduled check (server restart detection)
                state = await db.monitor_state.find_one({"_id": "main"})
                if state and state.get("next_check_utc"):
                    next_check_utc = state["next_check_utc"]
                    if isinstance(next_check_utc, str):
                        next_check_utc = datetime.fromisoformat(next_check_utc.replace('Z', '+00:00'))
                    if next_check_utc.tzinfo is None:
                        next_check_utc = next_check_utc.replace(tzinfo=timezone.utc)
                    
                    now_utc = datetime.now(timezone.utc)
                    if next_check_utc < now_utc:
                        minutes_overdue = (now_utc - next_check_utc).total_seconds() / 60
                        if minutes_overdue > 2:  # More than 2 minutes overdue
                            now_arizona = datetime.now(arizona_tz)
                            logger.warning(f"SERVER RESTART DETECTED! Missed check was {minutes_overdue:.0f} min overdue.")
                            
                            # Send alert to Telegram about the restart - auto-delete after 30 min
                            try:
                                telegram_config = await db.telegram_config.find_one({}, {"_id": 0})
                                if telegram_config and telegram_config.get("bot_token"):
                                    bot = Bot(token=telegram_config["bot_token"])
                                    msg = f"⚠️ *SERVER RESTART*\n\nMonitoring was interrupted.\nMissed check by ~{minutes_overdue:.0f} min.\nRunning immediate catch-up check.\n\nTime: {now_arizona.strftime('%I:%M %p')} Arizona"
                                    sent_msg = await bot.send_message(
                                        chat_id=telegram_config["chat_id"],
                                        text=msg,
                                        parse_mode=ParseMode.MARKDOWN
                                    )
                                    # Schedule auto-deletion after 30 minutes
                                    asyncio.create_task(delete_message_later(bot, telegram_config["chat_id"], sent_msg.message_id, 30))
                            except Exception as e:
                                logger.error(f"Failed to send restart alert: {e}")
                
                # Start background monitoring loop
                asyncio.create_task(monitoring_loop())
                
                logger.info("Bet monitoring auto-started with background loop (7-15 min random intervals, paused 10:45 PM - 6:00 AM Arizona)")
            else:
                logger.info("Bet monitoring not auto-started (disabled in config)")
        else:
            logger.info("Bet monitoring not auto-started (no active connection)")
    except Exception as e:
        logger.error(f"Error auto-starting monitoring: {str(e)}")


async def monitoring_loop():
    """Background loop for bet monitoring - designed to be resilient to all errors and server restarts"""
    global monitoring_enabled
    from zoneinfo import ZoneInfo
    arizona_tz = ZoneInfo('America/Phoenix')
    
    logger.info("=" * 60)
    logger.info("MONITORING LOOP STARTED - This loop should NEVER stop")
    logger.info("=" * 60)
    
    loop_iteration = 0
    
    # On startup, check if we missed a scheduled check due to server restart
    try:
        state = await db.monitor_state.find_one({"_id": "main"})
        if state and state.get("next_check_utc"):
            next_check_utc = state["next_check_utc"]
            if isinstance(next_check_utc, str):
                next_check_utc = datetime.fromisoformat(next_check_utc.replace('Z', '+00:00'))
            if next_check_utc.tzinfo is None:
                next_check_utc = next_check_utc.replace(tzinfo=timezone.utc)
            
            now_utc = datetime.now(timezone.utc)
            if next_check_utc < now_utc:
                # We missed a check! Calculate how overdue
                minutes_overdue = (now_utc - next_check_utc).total_seconds() / 60
                logger.warning(f"MISSED CHECK DETECTED! Was scheduled for {next_check_utc.isoformat()}, now {minutes_overdue:.1f} min overdue. Running immediately!")
                # Run immediately by not sleeping on first iteration
    except Exception as e:
        logger.error(f"Error checking for missed checks: {e}")
    
    while True:
        loop_iteration += 1
        try:
            if monitoring_enabled:
                # Check if we're in sleep hours
                now_arizona = datetime.now(arizona_tz)
                current_hour = now_arizona.hour
                current_minute = now_arizona.minute
                current_time_minutes = current_hour * 60 + current_minute
                
                sleep_start = 22 * 60 + 45  # 10:45 PM
                sleep_end = 6 * 60 + 0       # 6:00 AM
                
                if current_time_minutes >= sleep_start or current_time_minutes < sleep_end:
                    logger.info(f"[Loop #{loop_iteration}] Sleep hours ({now_arizona.strftime('%I:%M %p')} Arizona) - waiting 5 min...")
                    await asyncio.sleep(300)  # Check again in 5 minutes during sleep
                    continue
                
                # Run monitoring check - wrapped in its own try/except
                logger.info(f"[Loop #{loop_iteration}] Starting monitoring cycle...")
                try:
                    await run_monitoring_cycle()
                    logger.info(f"[Loop #{loop_iteration}] Monitoring cycle completed successfully")
                except Exception as e:
                    logger.error(f"[Loop #{loop_iteration}] Monitoring cycle error (loop continues): {str(e)}", exc_info=True)
                
                # Random sleep between 7-15 minutes
                next_interval = random.randint(MIN_INTERVAL, MAX_INTERVAL)
                next_check_time = now_arizona + timedelta(minutes=next_interval)
                next_check_utc = datetime.now(timezone.utc) + timedelta(minutes=next_interval)
                
                # CRITICAL: Store next check time in database so we can detect missed checks after restart
                try:
                    await db.monitor_state.update_one(
                        {"_id": "main"},
                        {"$set": {
                            "next_check_utc": next_check_utc.isoformat(),
                            "next_check_arizona": next_check_time.strftime('%I:%M %p'),
                            "last_check_utc": datetime.now(timezone.utc).isoformat(),
                            "loop_iteration": loop_iteration
                        }},
                        upsert=True
                    )
                except Exception as e:
                    logger.error(f"Failed to save monitor state: {e}")
                
                logger.info(f"[Loop #{loop_iteration}] Sleeping for {next_interval} minutes. Next check at ~{next_check_time.strftime('%I:%M %p')} Arizona")
                await asyncio.sleep(next_interval * 60)
                
            else:
                # Monitoring disabled, check status again in 1 minute
                logger.info(f"[Loop #{loop_iteration}] Monitoring disabled, checking status in 60s...")
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            logger.warning("Monitoring loop received CancelledError - this should only happen on shutdown")
            break
        except Exception as e:
            # This catch-all ensures the loop NEVER dies
            logger.error(f"[Loop #{loop_iteration}] UNEXPECTED ERROR in monitoring loop (will retry in 60s): {str(e)}", exc_info=True)
            await asyncio.sleep(60)  # Wait 1 minute before retrying
            continue  # Explicitly continue the loop


async def run_monitoring_cycle():
    """Run a single monitoring cycle with notifications"""
    from zoneinfo import ZoneInfo
    arizona_tz = ZoneInfo('America/Phoenix')
    check_time = datetime.now(arizona_tz)
    new_bets_found = {"jac075": 0, "jac083": 0}  # Default value
    
    try:
        # Log to database
        await db.activity_log.insert_one({
            "type": "bet_check",
            "account": "jac083",
            "timestamp": datetime.now(timezone.utc),
            "timestamp_arizona": check_time.strftime('%I:%M %p'),
            "date": check_time.strftime('%Y-%m-%d')
        })
        
        # Run monitoring
        logger.info(f"Running monitoring cycle at {check_time.strftime('%I:%M %p')} Arizona")
        
        try:
            result = await monitor_open_bets()
            if result is not None:
                new_bets_found = result
        except Exception as e:
            logger.error(f"Error in monitor_open_bets: {str(e)}", exc_info=True)
        
        # Check for settled bets
        try:
            await check_bet_results()
        except Exception as e:
            logger.error(f"Error in check_bet_results: {str(e)}", exc_info=True)
        
        # Send check notification (always try to send)
        try:
            await send_check_notification(check_time, new_bets_found)
        except Exception as e:
            logger.error(f"Error sending check notification: {str(e)}", exc_info=True)
        
    except Exception as e:
        logger.error(f"Monitoring cycle error: {str(e)}", exc_info=True)


async def startup_recovery():
    """Check if we missed overnight period and send catch-up notifications"""
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        now_arizona = datetime.now(arizona_tz)
        
        # Check when the last monitoring check happened
        last_activity = await db.activity_log.find_one({}, sort=[("timestamp", -1)])
        
        if last_activity:
            last_check = last_activity.get("timestamp")
            if last_check:
                # Handle both datetime objects and ISO strings
                if isinstance(last_check, str):
                    last_check = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                
                # If last_check is naive, assume UTC
                if last_check.tzinfo is None:
                    last_check = last_check.replace(tzinfo=timezone.utc)
                
                hours_since_last = (datetime.now(timezone.utc) - last_check).total_seconds() / 3600
                
                # Also check if a scheduled check was missed
                next_check = await get_next_check_time()
                check_was_missed = False
                if next_check:
                    if isinstance(next_check, str):
                        next_check = datetime.fromisoformat(next_check.replace('Z', '+00:00'))
                    if next_check.tzinfo is None:
                        next_check = next_check.replace(tzinfo=timezone.utc)
                    
                    # If next_check time has passed, we missed a check
                    if next_check < datetime.now(timezone.utc):
                        minutes_overdue = (datetime.now(timezone.utc) - next_check).total_seconds() / 60
                        if minutes_overdue > 2:  # More than 2 minutes overdue
                            check_was_missed = True
                            logger.warning(f"Startup recovery: Scheduled check was {minutes_overdue:.0f} minutes overdue!")
                
                if hours_since_last > 1 or check_was_missed:  # More than 1 hour gap OR missed scheduled check
                    logger.warning(f"Startup recovery: {hours_since_last:.1f} hours since last check. Sending catch-up notification...")
                    
                    # Send notification about the gap - auto-delete after 30 min
                    telegram_config = await db.telegram_config.find_one({}, {"_id": 0})
                    if telegram_config and telegram_config.get("bot_token") and telegram_config.get("chat_id"):
                        try:
                            bot = Bot(token=telegram_config["bot_token"])
                            msg = f"⚠️ *SYSTEM RESTART*\n\nServer restarted"
                            if hours_since_last > 1:
                                msg += f" after {hours_since_last:.1f} hours offline"
                            msg += f".\nRunning immediate check.\n\nTime: {now_arizona.strftime('%I:%M %p')} Arizona"
                            
                            sent_msg = await bot.send_message(
                                chat_id=telegram_config["chat_id"],
                                text=msg,
                                parse_mode=ParseMode.MARKDOWN
                            )
                            logger.info("Startup recovery notification sent")
                            # Schedule auto-deletion after 30 minutes
                            asyncio.create_task(delete_message_later(bot, telegram_config["chat_id"], sent_msg.message_id, 30))
                        except Exception as e:
                            logger.error(f"Failed to send startup notification: {e}")
                    
                    # Trigger immediate bet check (use the full cycle with notification)
                    logger.info("Triggering immediate catch-up bet check...")
                    asyncio.create_task(monitor_and_reschedule())
                else:
                    logger.info(f"Startup recovery: Last check was {hours_since_last:.1f} hours ago, no recovery needed")
        else:
            logger.info("Startup recovery: No previous activity found, skipping recovery")
            
    except Exception as e:
        logger.error(f"Startup recovery error: {str(e)}")


# Models
class ConnectionConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    password_encrypted: str
    website: str = "plays888.co"
    is_connected: bool = False
    last_connection: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ConnectionCreate(BaseModel):
    username: str
    password: str

class BettingRule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    enabled: bool = True
    min_odds: Optional[int] = None  # American odds (e.g., -110, +150)
    max_odds: Optional[int] = None  # American odds (e.g., -110, +150)
    wager_amount: float
    auto_place: bool = False
    sport: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BettingRuleCreate(BaseModel):
    name: str
    enabled: bool = True
    min_odds: Optional[int] = None  # American odds (e.g., -110, +150)
    max_odds: Optional[int] = None  # American odds (e.g., -110, +150)
    wager_amount: float
    auto_place: bool = False
    sport: Optional[str] = None

class BetOpportunity(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_name: str
    odds: int  # American odds (e.g., -110, +150)
    sport: str
    bet_type: str
    available: bool = True
    matched_rule_id: Optional[str] = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BetHistory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_id: str
    rule_id: str
    wager_amount: float
    odds: int  # American odds (e.g., -110, +150)
    status: str  # placed, won, lost, pending
    placed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    result: Optional[str] = None

class PlaceBetRequest(BaseModel):
    opportunity_id: str
    wager_amount: float

class AccountStatus(BaseModel):
    is_connected: bool
    balance: Optional[float] = None
    username: Optional[str] = None
    last_sync: Optional[datetime] = None


# Helper functions
def encrypt_password(password: str) -> str:
    return cipher_suite.encrypt(password.encode()).decode()

def decrypt_password(encrypted: str) -> str:
    return cipher_suite.decrypt(encrypted.encode()).decode()

def calculate_american_odds_payout(wager: float, odds: int) -> float:
    """Calculate potential payout from American odds"""
    if odds > 0:
        # Positive odds: shows profit on $100 bet
        return wager * (odds / 100)
    else:
        # Negative odds: shows how much to bet to win $100
        return wager * (100 / abs(odds))

def format_american_odds(odds: int) -> str:
    """Format American odds with + or - sign"""
    return f"+{odds}" if odds > 0 else str(odds)

# Account username to display name mapping
ACCOUNT_LABELS = {
    "jac075": "ENANO",
    "jac083": "TIPSTER"
}

def format_amount_short(amount: float) -> str:
    """Format amount as short string like $2.2K"""
    if amount >= 1000:
        return f"${amount/1000:.1f}K".replace('.0K', 'K')
    return f"${amount:.0f}"

def extract_short_game_name(game: str, description: str = "") -> str:
    """Extract VERY short team names - max 3-4 chars per team"""
    import re
    
    text = (game or description or "").upper()
    
    # Common team abbreviations dictionary
    TEAM_ABBREVS = {
        # NFL
        'JACKSONVILLE': 'JAX', 'JAGUARS': 'JAX', 'DENVER': 'DEN', 'BRONCOS': 'DEN',
        'ATLANTA': 'ATL', 'FALCONS': 'ATL', 'ARIZONA': 'ARI', 'CARDINALS': 'ARI',
        'PITTSBURGH': 'PIT', 'STEELERS': 'PIT', 'PENGUINS': 'PIT',
        'DETROIT': 'DET', 'LIONS': 'DET', 'PATRIOTS': 'NE', 'NEW ENGLAND': 'NE',
        'BALTIMORE': 'BAL', 'RAVENS': 'BAL', 'LAS VEGAS': 'LV', 'RAIDERS': 'LV',
        'HOUSTON': 'HOU', 'TEXANS': 'HOU',
        # NHL
        'WINNIPEG': 'WPG', 'JETS': 'WPG', 'UTAH': 'UTA', 'MAMMOTH': 'UTA',
        'COLORADO': 'COL', 'AVALANCHE': 'COL', 'MINNESOTA': 'MIN', 'WILD': 'MIN',
        'MONTREAL': 'MTL', 'CANADIENS': 'MTL', 'NEW YORK': 'NY', 'RANGERS': 'NYR',
        'NASHVILLE': 'NSH', 'PREDATORS': 'NSH',
        # College Basketball common
        'SACRAMENTO': 'SAC', 'STATE': '', 'BETHUNE': 'BETH', 'COOKMAN': 'COOK',
        'CENTRAL': 'CEN', 'MICHIGAN': 'MICH', 'FAIRLEIGH': 'FDU', 'DICKINSON': 'FDU',
        'INDIANAPOLIS': 'INDY', 'IRVINE': 'UCI', 'NORFOLK': 'NORF',
        'CREIGHTON': 'CRE', 'EDWARDSVILLE': 'SIU', 'TECH': 'TCH',
        'ALABAMA': 'ALA', 'KENTUCKY': 'KEN', 'DUKE': 'DUKE', 'CAROLINA': 'CAR',
        'GONZAGA': 'GONZ', 'VILLANOVA': 'NOVA', 'KANSAS': 'KAN', 'TEXAS': 'TEX',
        'FLORIDA': 'FLA', 'OHIO': 'OHIO', 'OREGON': 'ORE', 'UCLA': 'UCLA',
        'MEMPHIS': 'MEM', 'TENNESSEE': 'TENN', 'VIRGINIA': 'UVA', 'LOUISVILLE': 'LOU',
        'XAVIER': 'XAV', 'PURDUE': 'PUR', 'ILLINOIS': 'ILL', 'IOWA': 'IOWA',
        'WISCONSIN': 'WISC', 'MARYLAND': 'MD', 'INDIANA': 'IND', 'PENN': 'PENN',
        'SYRACUSE': 'SYR', 'CLEMSON': 'CLEM', 'MIAMI': 'MIA', 'AUBURN': 'AUB',
        'ARKANSAS': 'ARK', 'MISSISSIPPI': 'MISS', 'MISSOURI': 'MIZZ', 'BAYLOR': 'BAY',
        'STANFORD': 'STAN', 'WASHINGTON': 'WASH', 'ARIZONA STATE': 'ASU',
        'BOSTON': 'BOS', 'COLLEGE': 'BC', 'CONNECTICUT': 'UCON', 'TEMPLE': 'TEM',
        'CINCINNATI': 'CIN', 'HOUSTON': 'HOU', 'SMU': 'SMU', 'TULANE': 'TUL',
        'RICE': 'RICE', 'PEPPERDINE': 'PEP', 'NEW MEXICO': 'NM', 'MEXICO': 'NM',
        # Soccer
        'ABHA': 'ABHA', 'CLUB': '',
        # Generic
        'UNIVERSITY': '', 'OF': '', 'THE': '', 'VRS': '', 'VS': '', 'REG.TIME': '', 'REG': '',
    }
    
    def get_abbrev(team_name):
        """Get abbreviation for a team name"""
        team_name = team_name.strip().upper()
        
        # Direct lookup
        if team_name in TEAM_ABBREVS:
            return TEAM_ABBREVS[team_name]
        
        # Try each word
        words = team_name.split()
        abbrev_parts = []
        for word in words:
            if word in TEAM_ABBREVS:
                if TEAM_ABBREVS[word]:  # Skip empty abbreviations
                    abbrev_parts.append(TEAM_ABBREVS[word])
            elif len(word) >= 3:
                abbrev_parts.append(word[:3])
        
        if abbrev_parts:
            return abbrev_parts[0]  # Return first significant part
        
        # Fallback: first 4 chars
        return team_name[:4] if team_name else "TM"
    
    # Remove common noise
    text = re.sub(r'REG\.?TIME|OT INCLUDED|\[.*?\]|\d{1,3}\s*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Try to find matchup pattern
    match = re.search(r'(.+?)\s*(?:VRS|VS\.?|@|\/)\s*(.+)', text, re.IGNORECASE)
    if match:
        team1 = get_abbrev(match.group(1).strip())
        team2 = get_abbrev(match.group(2).strip())
        return f"{team1}/{team2}"
    
    # Single team (like spreads)
    return get_abbrev(text)

def extract_bet_type_short(bet_type: str) -> str:
    """Extract short bet type like 'u48' or 'o47' from bet description"""
    import re
    
    if not bet_type:
        return ""
    
    # Look for over/under patterns
    over_match = re.search(r'(?:over|o)\s*(\d+(?:\.\d+)?)', bet_type, re.IGNORECASE)
    if over_match:
        return f"o{over_match.group(1)}"
    
    under_match = re.search(r'(?:under|u)\s*(\d+(?:\.\d+)?)', bet_type, re.IGNORECASE)
    if under_match:
        return f"u{under_match.group(1)}"
    
    # Look for spread patterns
    spread_match = re.search(r'([+-]?\d+(?:\.\d+)?)', bet_type)
    if spread_match:
        return spread_match.group(1)
    
    # Return truncated original
    return bet_type[:15] if len(bet_type) > 15 else bet_type

async def get_or_create_daily_compilation(account: str) -> dict:
    """Get or create the daily bet compilation for an account"""
    from zoneinfo import ZoneInfo
    arizona_tz = ZoneInfo('America/Phoenix')
    today = datetime.now(arizona_tz).strftime('%Y-%m-%d')
    
    compilation = await db.daily_compilations.find_one({
        "account": account,
        "date": today
    })
    
    if not compilation:
        compilation = {
            "account": account,
            "date": today,
            "message_id": None,
            "bets": [],
            "total_result": 0,
            "created_at": datetime.now(timezone.utc)
        }
        await db.daily_compilations.insert_one(compilation)
    
    return compilation

async def build_compilation_message(account: str) -> str:
    """Build the compilation message for an account"""
    from zoneinfo import ZoneInfo
    arizona_tz = ZoneInfo('America/Phoenix')
    today = datetime.now(arizona_tz).strftime('%Y-%m-%d')
    
    compilation = await db.daily_compilations.find_one({
        "account": account,
        "date": today
    })
    
    if not compilation or not compilation.get('bets'):
        return None
    
    account_label = ACCOUNT_LABELS.get(account, account)
    bets = compilation['bets']
    total_result = compilation.get('total_result', 0)
    
    lines = [f"👤 *{account_label}*", ""]
    
    for i, bet in enumerate(bets, 1):
        game_short = bet.get('game_short', 'GAME')
        bet_type_short = bet.get('bet_type_short', '')
        wager_short = bet.get('wager_short', '$0')
        to_win_short = bet.get('to_win_short', '$0')
        result = bet.get('result')  # None, 'won', 'lost', 'push'
        
        # Build compact line: #1 TEAM/TEAM o47 ($2.2K/$2K)🟡
        bet_line = f"#{i} {game_short}"
        if bet_type_short:
            bet_line += f" {bet_type_short}"
        bet_line += f" ({wager_short}/{to_win_short})"
        
        # Add result emoji - 🟡 for pending, 🟢 won, 🔴 lost, 🔵 push
        if result == 'won':
            bet_line += "🟢"
        elif result == 'lost':
            bet_line += "🔴"
        elif result == 'push':
            bet_line += "🔵"
        else:
            bet_line += "🟡"  # Pending
        
        lines.append(bet_line)
    
    # Add result total if any bets are settled
    settled_bets = [b for b in bets if b.get('result') in ['won', 'lost', 'push']]
    if settled_bets:
        lines.append("")
        result_sign = "+" if total_result >= 0 else ""
        lines.append(f"*Result: {result_sign}{format_amount_short(total_result)}*")
    
    return "\n".join(lines)

async def update_compilation_message(account: str):
    """Update the Telegram message for the daily compilation - deletes old and sends new to keep at bottom of chat"""
    if not telegram_bot or not telegram_chat_id:
        logger.info("Telegram not configured, skipping compilation update")
        return
    
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        today = datetime.now(arizona_tz).strftime('%Y-%m-%d')
        
        compilation = await db.daily_compilations.find_one({
            "account": account,
            "date": today
        })
        
        if not compilation or not compilation.get('bets'):
            return
        
        message_text = await build_compilation_message(account)
        if not message_text:
            return
        
        # Delete ALL old messages for this account (today and previous days)
        all_compilations = await db.daily_compilations.find({"account": account}).to_list(100)
        for old_comp in all_compilations:
            old_message_id = old_comp.get('message_id')
            if old_message_id:
                try:
                    await telegram_bot.delete_message(
                        chat_id=telegram_chat_id,
                        message_id=old_message_id
                    )
                    logger.info(f"Deleted old compilation message {old_message_id} for {account}")
                except Exception as e:
                    logger.debug(f"Could not delete old message {old_message_id}: {e}")
                
                # Clear the message_id in database
                await db.daily_compilations.update_one(
                    {"_id": old_comp["_id"]},
                    {"$set": {"message_id": None}}
                )
        
        # Send new message (always at bottom of chat)
        sent_message = await telegram_bot.send_message(
            chat_id=telegram_chat_id,
            text=message_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Store the new message ID for today's compilation
        await db.daily_compilations.update_one(
            {"account": account, "date": today},
            {"$set": {"message_id": sent_message.message_id}}
        )
        logger.info(f"Sent new compilation message for {account}, message_id: {sent_message.message_id}")
        
        # Clean up old compilations from database (keep only last 7 days)
        seven_days_ago = (datetime.now(arizona_tz) - timedelta(days=7)).strftime('%Y-%m-%d')
        await db.daily_compilations.delete_many({
            "account": account,
            "date": {"$lt": seven_days_ago}
        })
    
    except Exception as e:
        logger.error(f"Failed to update compilation message: {str(e)}")

async def add_bet_to_compilation(account: str, bet_details: dict):
    """Add a new bet to the daily compilation and update Telegram"""
    from zoneinfo import ZoneInfo
    arizona_tz = ZoneInfo('America/Phoenix')
    today = datetime.now(arizona_tz).strftime('%Y-%m-%d')
    
    # Prepare bet entry
    game = bet_details.get('game', '')
    description = bet_details.get('description', '')
    bet_type = bet_details.get('bet_type', '')
    wager = bet_details.get('wager', 0)
    to_win = bet_details.get('potential_win', wager)
    ticket = bet_details.get('ticket_number', '')
    
    bet_entry = {
        "ticket": ticket,
        "game": game,
        "game_short": extract_short_game_name(game, description),
        "bet_type": bet_type,
        "bet_type_short": extract_bet_type_short(bet_type),
        "wager": wager,
        "wager_short": format_amount_short(wager),
        "to_win": to_win,
        "to_win_short": format_amount_short(to_win),
        "result": None,
        "added_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Ensure compilation exists
    compilation = await db.daily_compilations.find_one({
        "account": account,
        "date": today
    })
    
    if not compilation:
        compilation = {
            "account": account,
            "date": today,
            "message_id": None,
            "bets": [],
            "total_result": 0,
            "created_at": datetime.now(timezone.utc)
        }
        await db.daily_compilations.insert_one(compilation)
    
    # Add bet to compilation
    await db.daily_compilations.update_one(
        {"account": account, "date": today},
        {"$push": {"bets": bet_entry}}
    )
    
    # Update Telegram message
    await update_compilation_message(account)
    logger.info(f"Added bet to compilation for {account}: {bet_entry['game_short']}")

async def update_bet_result_in_compilation(account: str, ticket: str, result: str, win_amount: float = 0):
    """Update a bet's result in the compilation and update Telegram"""
    from zoneinfo import ZoneInfo
    arizona_tz = ZoneInfo('America/Phoenix')
    today = datetime.now(arizona_tz).strftime('%Y-%m-%d')
    
    compilation = await db.daily_compilations.find_one({
        "account": account,
        "date": today
    })
    
    if not compilation:
        logger.warning(f"No compilation found for {account} on {today}")
        return
    
    bets = compilation.get('bets', [])
    total_result = compilation.get('total_result', 0)
    
    # Find and update the bet
    for bet in bets:
        if bet.get('ticket') == ticket and bet.get('result') is None:
            bet['result'] = result
            if result == 'won':
                total_result += win_amount
            elif result == 'lost':
                total_result -= bet.get('wager', 0)
            # push doesn't change total
            break
    
    # Update in database
    await db.daily_compilations.update_one(
        {"account": account, "date": today},
        {"$set": {"bets": bets, "total_result": total_result}}
    )
    
    # Update Telegram message
    await update_compilation_message(account)
    logger.info(f"Updated result for ticket {ticket} in {account}'s compilation: {result}")

async def send_telegram_notification(bet_details: dict, account: str = None):
    """Send Telegram notification when a bet is placed - now uses compilation system"""
    if not telegram_bot or not telegram_chat_id:
        logger.info("Telegram not configured, skipping notification")
        return
    
    try:
        # Add to daily compilation instead of sending individual message
        await add_bet_to_compilation(account, bet_details)
        logger.info(f"Telegram compilation updated for Ticket#{bet_details.get('ticket_number')}")
        
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {str(e)}")


async def get_plays888_daily_totals(username: str, password: str) -> dict:
    """Scrape daily totals directly from plays888.co History page using Win/Loss row"""
    service = None
    try:
        service = Plays888Service()
        await service.initialize()
        
        login_result = await service.login(username, password)
        if not login_result["success"]:
            logger.error(f"Login failed for {username}: {login_result['message']}")
            return None
        
        # Go to History page
        await service.page.goto('https://www.plays888.co/wager/History.aspx', timeout=30000)
        await service.page.wait_for_timeout(4000)
        
        # Extract the daily summary table
        # The Win/Loss row has the actual daily profits directly - much more reliable
        # Supports both English (Mon, Tue, etc.) and Spanish (lun, mar, etc.) headers
        totals = await service.page.evaluate('''() => {
            const result = {
                daily_profits: [],
                week_total: null,
                win_loss_row: [],
                detected_language: null,
                debug_header: [],
                error: null
            };
            
            // Standard day names (we'll normalize everything to these)
            const standardDays = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
            
            // Mapping from Spanish to English
            const spanishToEnglish = {
                'lun': 'mon',
                'mar': 'tue',
                'mié': 'wed',
                'mi\u00e9': 'wed',
                'mie': 'wed',
                'jue': 'thu',
                'vie': 'fri',
                'sáb': 'sat',
                's\u00e1b': 'sat',
                'sab': 'sat',
                'dom': 'sun'
            };
            
            try {
                const tables = document.querySelectorAll('table');
                
                for (const table of tables) {
                    const text = table.textContent.trim().toLowerCase();
                    
                    // Look for summary table - check for both English and Spanish patterns
                    const hasSpanishDays = text.includes('lun') && text.includes('mar') && text.includes('jue');
                    const hasEnglishDays = text.includes('mon') && text.includes('tue') && text.includes('thu');
                    const hasBeginning = text.includes('beginning');
                    
                    if (hasBeginning || hasSpanishDays || hasEnglishDays) {
                        const rows = table.querySelectorAll('tr');
                        
                        // Build header-to-day mapping from FIRST row
                        // Header: [empty, Beginning, Mon/lun, Tue/mar, Wed/mié, Thu/jue, Fri/vie, Sat/sáb, Sun/dom, Total]
                        // Index:   0      1          2        3        4        5        6        7        8        9
                        let headerDayMap = {}; // Maps cell index to normalized day name
                        
                        const firstRow = rows[0];
                        if (firstRow) {
                            const headerCells = firstRow.querySelectorAll('td, th');
                            result.debug_header = Array.from(headerCells).map(c => c.textContent.trim());
                            
                            for (let i = 0; i < headerCells.length; i++) {
                                let dayText = headerCells[i].textContent.trim().toLowerCase().replace(/\\xa0/g, ' ').replace(/\\s+/g, '');
                                
                                // Check Spanish days first
                                if (spanishToEnglish[dayText]) {
                                    headerDayMap[i] = spanishToEnglish[dayText];
                                    result.detected_language = 'spanish';
                                }
                                // Check English days
                                else if (standardDays.includes(dayText.substring(0, 3))) {
                                    headerDayMap[i] = dayText.substring(0, 3);
                                    result.detected_language = result.detected_language || 'english';
                                }
                                // Check for 'total'
                                else if (dayText.includes('total')) {
                                    headerDayMap[i] = 'total';
                                }
                                // Check for 'beginning'
                                else if (dayText.includes('beginning')) {
                                    headerDayMap[i] = 'beginning';
                                }
                            }
                        }
                        
                        // Find Win/Loss row and extract values using headerDayMap
                        for (const row of rows) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length < 2) continue;
                            
                            const firstCell = cells[0].textContent.trim().toLowerCase();
                            
                            // Win/Loss row has the daily profits directly
                            if (firstCell.includes('win') || firstCell.includes('loss')) {
                                for (let i = 1; i < cells.length; i++) {
                                    const cellText = cells[i].textContent.trim();
                                    const match = cellText.match(/(-?[\\d,]+\\.\\d+)/);
                                    if (match) {
                                        const profit = parseFloat(match[1].replace(/,/g, ''));
                                        // Use headerDayMap to get the day name for this column
                                        const dayName = headerDayMap[i] || ('col' + i);
                                        result.win_loss_row.push({
                                            day: dayName,
                                            profit: profit
                                        });
                                    }
                                }
                                break;
                            }
                        }
                        
                        // Use Win/Loss row for daily profits
                        if (result.win_loss_row.length > 0) {
                            // Filter out Total, Beginning, and unknown columns for daily_profits
                            result.daily_profits = result.win_loss_row.filter(d => 
                                d.day !== 'total' && d.day !== 'beginning' && !d.day.startsWith('col')
                            );
                            // Get week total
                            const total = result.win_loss_row.find(d => d.day === 'total');
                            if (total) {
                                result.week_total = total.profit;
                            } else {
                                // Sum up all days if Total not found
                                result.week_total = result.daily_profits.reduce((sum, d) => sum + d.profit, 0);
                            }
                        }
                        
                        break;
                    }
                }
                
                // Count bet rows from the bet history table (rows with dates and dollar amounts)
                // Exclude ACCRUAL ADJUSTMENT rows which aren't actual bets
                result.total_bets = 0;
                const allTables = document.querySelectorAll('table');
                for (const table of allTables) {
                    const rows = table.querySelectorAll('tr');
                    for (const row of rows) {
                        const text = row.textContent;
                        // Bet rows have date format (MM/DD/YYYY) and Ticket #
                        // Exclude ACCRUAL ADJUSTMENT rows
                        if (text.match(/\\d{1,2}\\/\\d{1,2}\\/\\d{4}/) && 
                            text.match(/Ticket #:/i) && 
                            !text.toUpperCase().includes('ACCRUAL')) {
                            result.total_bets++;
                        }
                    }
                }
                
            } catch (e) {
                result.error = e.toString();
            }
            
            return result;
        }''')
        
        await service.close()
        logger.info(f"plays888 totals for {username}: {totals}")
        return totals
        
    except Exception as e:
        logger.error(f"Error getting plays888 totals: {str(e)}")
        if service:
            try:
                await service.close()
            except:
                pass
        return None


async def send_daily_summary():
    """Send daily betting summary to Telegram at 10:45 PM Arizona time"""
    if not telegram_bot or not telegram_chat_id:
        logger.info("Telegram not configured, skipping daily summary")
        return
    
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        now_arizona = datetime.now(arizona_tz)
        
        # Get day of week for matching plays888 data
        day_names_es = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']
        day_names_en = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        today_dow = now_arizona.weekday()  # 0=Monday
        today_day_es = day_names_es[today_dow]
        today_day_en = day_names_en[today_dow]
        
        # Get accounts
        connections = await db.connections.find({"is_connected": True}, {"_id": 0}).to_list(100)
        
        for conn in connections:
            username = conn["username"]
            password = decrypt_password(conn["password_encrypted"])
            label = ACCOUNT_LABELS.get(username, username)
            
            # Get plays888 daily totals
            totals = await get_plays888_daily_totals(username, password)
            
            if totals and totals.get('daily_profits'):
                # Day names are now normalized to English lowercase (mon, tue, wed, thu, fri, sat, sun)
                day_display_names = {
                    'mon': 'Monday', 'tue': 'Tuesday', 'wed': 'Wednesday',
                    'thu': 'Thursday', 'fri': 'Friday', 'sat': 'Saturday', 'sun': 'Sunday'
                }
                
                # Find today's profit using normalized day name
                today_profit = None
                for day_data in totals['daily_profits']:
                    day = day_data['day'].lower()
                    if day == today_day_en or day.startswith(today_day_en):
                        today_profit = day_data['profit']
                        break
                
                # Build week summary
                week_lines = []
                for day_data in totals['daily_profits']:
                    amt = day_data['profit']
                    emoji = "📈" if amt >= 0 else "📉"
                    day_name = day_display_names.get(day_data['day'], day_data['day'].capitalize())
                    week_lines.append(f"{emoji} {day_name}: ${amt:+,.2f}")
                
                week_text = "\n".join(week_lines) if week_lines else "No data"
                
                # Week total
                week_total = totals.get('week_total', 0)
                week_emoji = "📈" if week_total >= 0 else "📉"
                
                if today_profit is not None:
                    profit_emoji = "📈" if today_profit >= 0 else "📉"
                    profit_text = f"{profit_emoji} *Today's Profit:* ${today_profit:+,.2f} MXN"
                else:
                    profit_text = "⚠️ Could not get today's profit"
                
                message = f"""
📊 *{label} - DAILY SUMMARY*
📅 {now_arizona.strftime('%B %d, %Y')}

{profit_text}

📆 *This Week:*
{week_text}

{week_emoji} *Week Total:* ${week_total:+,.2f} MXN

_Data from plays888.co_
_Have a good night! 🌙_
                """
            else:
                message = f"""
📊 *{label} - DAILY SUMMARY*
📅 {now_arizona.strftime('%B %d, %Y')}

⚠️ Could not retrieve data from plays888.co

_Have a good night! 🌙_
                """
            
            await telegram_bot.send_message(
                chat_id=telegram_chat_id,
                text=message.strip(),
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"Daily summary sent for {label}")
        
        logger.info(f"Daily summaries sent")
        
    except Exception as e:
        logger.error(f"Failed to send daily summary: {str(e)}")


async def send_user_daily_summary(account: str, label: str, user_bets: list, now_arizona):
    """Send daily summary for a specific user"""
    try:
        # Filter out garbage entries (bets with $0 wager or no ticket)
        user_bets = [b for b in user_bets if b.get('wager_amount', 0) > 0 and b.get('bet_slip_id')]
        
        if not user_bets:
            message = f"""
📊 *{label} - DAILY SUMMARY*
📅 {now_arizona.strftime('%B %d, %Y')}

No bets placed today.

_Have a good night! 🌙_
            """
        else:
            total_wagered = sum(b.get('wager_amount', 0) for b in user_bets)
            
            # Calculate results
            won_bets = [b for b in user_bets if b.get('result') == 'won']
            lost_bets = [b for b in user_bets if b.get('result') == 'lost']
            push_bets = [b for b in user_bets if b.get('result') == 'push']
            pending_bets = [b for b in user_bets if not b.get('result') or b.get('result') == 'pending']
            
            total_won = sum(b.get('win_amount', 0) for b in won_bets)
            total_lost = sum(b.get('wager_amount', 0) for b in lost_bets)
            net_profit = total_won - total_lost
            
            # Build bet list with results
            bet_lines = []
            for i, bet in enumerate(user_bets[:15], 1):  # Limit to 15 bets per user
                game = bet.get('game', 'Unknown')[:25]
                bet_type = bet.get('bet_type', '')[:12]
                odds = format_american_odds(bet.get('odds', -110))
                wager = bet.get('wager_amount', 0)
                result = bet.get('result', '')
                
                # Result emoji
                if result == 'won':
                    result_emoji = "✅"
                elif result == 'lost':
                    result_emoji = "❌"
                elif result == 'push':
                    result_emoji = "↔️"
                else:
                    result_emoji = "⏳"
                
                bet_lines.append(f"{result_emoji} {game} | {bet_type} {odds} | ${wager}")
            
            bets_text = "\n".join(bet_lines)
            if len(user_bets) > 15:
                bets_text += f"\n_... and {len(user_bets) - 15} more bets_"
            
            # Profit/Loss indicator
            if net_profit > 0:
                profit_text = f"📈 *Net Profit:* +${net_profit:,.2f} MXN"
            elif net_profit < 0:
                profit_text = f"📉 *Net Loss:* -${abs(net_profit):,.2f} MXN"
            else:
                profit_text = f"➡️ *Net:* $0.00 MXN"
            
            message = f"""
📊 *{label} - DAILY SUMMARY*
📅 {now_arizona.strftime('%B %d, %Y')}

📈 *Results:*
• Total Bets: {len(user_bets)}
• ✅ Won: {len(won_bets)} (${total_won:,.2f})
• ❌ Lost: {len(lost_bets)} (${total_lost:,.2f})
• ↔️ Push: {len(push_bets)}
• ⏳ Pending: {len(pending_bets)}

💰 *Financials:*
• Total Wagered: ${total_wagered:,.2f} MXN
{profit_text}

🎯 *Today's Bets:*
{bets_text}

_⚠️ Numbers may differ slightly from plays888 due to timing_
_Have a good night! 🌙_
            """
        
        await telegram_bot.send_message(
            chat_id=telegram_chat_id,
            text=message.strip(),
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"Daily summary sent for {label} ({len(user_bets)} bets)")
        
    except Exception as e:
        logger.error(f"Failed to send daily summary for {label}: {str(e)}")


async def send_activity_summary():
    """Send daily activity summary showing all check times - runs at 10:59 PM Arizona"""
    if not telegram_bot or not telegram_chat_id:
        logger.info("Telegram not configured, skipping activity summary")
        return
    
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        now_arizona = datetime.now(arizona_tz)
        today_date = now_arizona.strftime('%Y-%m-%d')
        
        # Get all checks from today for TIPSTER (jac083)
        today_checks = await db.activity_log.find({
            "date": today_date,
            "type": "bet_check",
            "account": "jac083"
        }, {"_id": 0}).sort("timestamp", 1).to_list(1000)
        
        if not today_checks:
            check_times_text = "No checks performed today."
        else:
            # Group checks by hour for cleaner display
            check_times = [c.get('timestamp_arizona', 'Unknown') for c in today_checks]
            
            # Format as a list
            if len(check_times) <= 30:
                check_times_text = " • ".join(check_times)
            else:
                # If many checks, show summary
                check_times_text = f"{len(check_times)} checks performed\n"
                check_times_text += f"First: {check_times[0]} | Last: {check_times[-1]}\n"
                check_times_text += " • ".join(check_times[-10:])  # Show last 10
        
        message = f"""
🔄 *TIPSTER ACTIVITY SUMMARY*
📅 {now_arizona.strftime('%B %d, %Y')}

👤 *Account:* TIPSTER (jac083)
📡 *System Checks:* {len(today_checks)}

⏰ *Check Times (Arizona):*
{check_times_text}

✅ *System Status:* Active
🕐 *Sleep Hours:* 10:45 PM - 6:00 AM

_Betting summaries follow..._
        """
        
        await telegram_bot.send_message(
            chat_id=telegram_chat_id,
            text=message.strip(),
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"Activity summary sent to Telegram ({len(today_checks)} checks)")
        
    except Exception as e:
        logger.error(f"Failed to send activity summary: {str(e)}")


async def daily_cleanup():
    """Clean up old data at 9 AM Arizona time"""
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        now_arizona = datetime.now(arizona_tz)
        
        # Clean up yesterday's activity logs (activity logs only kept for 1 day)
        yesterday = (now_arizona - timedelta(days=1)).strftime('%Y-%m-%d')
        activity_deleted = await db.activity_log.delete_many({"date": {"$lte": yesterday}})
        logger.info(f"Cleaned up {activity_deleted.deleted_count} old activity logs")
        
        # Clean up bet history older than 7 days
        seven_days_ago = (now_arizona - timedelta(days=7))
        old_bets_deleted = await db.bet_history.delete_many({
            "placed_at": {"$lt": seven_days_ago.isoformat()}
        })
        logger.info(f"Cleaned up {old_bets_deleted.deleted_count} old bet records (>7 days)")
        
    except Exception as e:
        logger.error(f"Failed to run daily cleanup: {str(e)}")


async def check_bet_results():
    """Check plays888.co for settled bet results and update database"""
    logger.info("Checking for settled bet results...")
    
    try:
        # Get all connections
        connections = await db.connections.find({"is_connected": True}, {"_id": 0}).to_list(100)
        
        if not connections:
            logger.info("No active connections, skipping results check")
            return
        
        for conn in connections:
            await check_results_for_account(conn)
            
    except Exception as e:
        logger.error(f"Error checking bet results: {str(e)}")


async def check_results_for_account(conn: dict):
    """Check settled bets for a single account"""
    username = conn["username"]
    password = decrypt_password(conn["password_encrypted"])
    
    logger.info(f"Checking results for account: {username}")
    results_service = None
    
    try:
        results_service = Plays888Service()
        await results_service.initialize()
        
        # Login
        login_result = await results_service.login(username, password)
        if not login_result["success"]:
            logger.error(f"Results login failed for {username}: {login_result['message']}")
            await results_service.close()
            return
        
        # Navigate to Bet History / Graded Bets page
        # Common URLs to try: GradedBets.aspx, BetHistory.aspx, History.aspx
        history_urls = [
            'https://www.plays888.co/wager/GradedBets.aspx',
            'https://www.plays888.co/wager/BetHistory.aspx',
            'https://www.plays888.co/wager/History.aspx',
            'https://www.plays888.co/wager/SettledBets.aspx'
        ]
        
        page_loaded = False
        for url in history_urls:
            try:
                await results_service.page.goto(url, timeout=15000)
                await results_service.page.wait_for_timeout(3000)
                
                # Check if page has content (not a 404 or redirect)
                content = await results_service.page.content()
                if 'Ticket' in content or 'ticket' in content:
                    logger.info(f"Found history page: {url}")
                    page_loaded = True
                    break
            except:
                continue
        
        if not page_loaded:
            logger.info(f"Could not find bet history page for {username}")
            await results_service.close()
            return
        
        # Extract settled bets from the page
        # First, let's get debug info - look for rows with Ticket numbers
        debug_info = await results_service.page.evaluate('''() => {
            const rows = document.querySelectorAll('table tr');
            const debug = [];
            // Look for rows containing ticket info
            for (let i = 0; i < rows.length; i++) {
                const text = rows[i].textContent;
                // Only log rows that might have ticket info
                if (text.includes('Ticket') || text.includes('337') || text.includes('Result')) {
                    debug.push({
                        idx: i,
                        text: text.substring(0, 400),
                        cells: rows[i].querySelectorAll('td').length
                    });
                }
            }
            return {rowCount: rows.length, ticketRows: debug};
        }''')
        logger.info(f"History page: {debug_info['rowCount']} total rows, {len(debug_info['ticketRows'])} with ticket/result info")
        for row in debug_info['ticketRows'][:5]:
            logger.info(f"Row {row['idx']} ({row['cells']} cells): {row['text']}")
        
        settled_bets = await results_service.page.evaluate('''() => {
            const bets = [];
            const rows = document.querySelectorAll('table tr');
            
            for (let i = 0; i < rows.length; i++) {
                const row = rows[i];
                const cells = row.querySelectorAll('td');
                const rowText = row.textContent || '';
                
                // Look for ticket numbers - handle "Ticket #: 337..." or "Ticket#: 337..."
                const ticketMatch = rowText.match(/Ticket\\s*#?\\s*:?\\s*(\\d{9})/i);
                
                if (ticketMatch && cells.length >= 3) {
                    const ticket = ticketMatch[1];
                    
                    // Look for result indicators
                    // plays888 shows "WINWIN" or "LOSELOSE" at the end of each row
                    let result = 'pending';
                    const rowTextUpper = rowText.toUpperCase();
                    
                    // Check for specific patterns in plays888 format
                    if (rowTextUpper.includes('WINWIN') || rowTextUpper.endsWith('WIN')) {
                        result = 'won';
                    } 
                    else if (rowTextUpper.includes('LOSELOSE') || rowTextUpper.endsWith('LOSE') || rowTextUpper.endsWith('LOSS')) {
                        result = 'lost';
                    } 
                    else if (rowTextUpper.includes('PUSHPUSH') || rowTextUpper.includes('PUSH')) {
                        result = 'push';
                    } 
                    else if (rowTextUpper.includes('CANCEL') || rowTextUpper.includes('VOID')) {
                        result = 'cancelled';
                    }
                    
                    // Extract win amount - format is "2000.00WINWIN" or "-2200.00LOSELOSE"
                    let winAmount = 0;
                    
                    // Look for amount right before WIN or LOSE
                    const amountBeforeResult = rowText.match(/([\\d,]+\\.\\d+)(?:WINWIN|WIN)/i);
                    if (amountBeforeResult && result === 'won') {
                        winAmount = parseFloat(amountBeforeResult[1].replace(/,/g, ''));
                    }
                    
                    // Also get the wager amount from Risk/Win format "2200.00 / 2000.00"
                    const riskWinMatch = rowText.match(/([\\d,]+\\.\\d+)\\s*\\/\\s*([\\d,]+\\.\\d+)/);
                    let wagerAmount = 0;
                    if (riskWinMatch) {
                        wagerAmount = parseFloat(riskWinMatch[1].replace(/,/g, ''));
                        if (result === 'won' && winAmount === 0) {
                            winAmount = parseFloat(riskWinMatch[2].replace(/,/g, ''));
                        }
                    }
                    
                    if (result !== 'pending') {
                        bets.push({
                            ticket: ticket,
                            result: result,
                            winAmount: winAmount,
                            rowText: rowText.substring(0, 200)  // For debugging
                        });
                    }
                }
            }
            return bets;
        }''')
        
        logger.info(f"Found {len(settled_bets)} settled bets for {username}")
        
        # Update database with results
        results_updated = 0
        for bet in settled_bets:
            ticket_num = bet.get('ticket')
            result = bet.get('result')
            win_amount = bet.get('winAmount', 0)
            
            # Find and update the bet in database
            existing_bet = await db.bet_history.find_one({"bet_slip_id": ticket_num})
            
            if existing_bet and existing_bet.get('result') != result:
                # Update the result
                await db.bet_history.update_one(
                    {"bet_slip_id": ticket_num},
                    {"$set": {
                        "result": result,
                        "win_amount": win_amount,
                        "result_updated_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                results_updated += 1
                logger.info(f"Updated Ticket#{ticket_num}: {result}")
                
                # Send Telegram notification for result
                await send_result_notification(existing_bet, result, win_amount, username)
        
        await results_service.close()
        logger.info(f"Results check complete for {username}: {results_updated} bets updated")
        
    except Exception as e:
        logger.error(f"Error checking results for {username}: {str(e)}")
        if results_service:
            try:
                await results_service.close()
            except:
                pass


async def send_result_notification(bet: dict, result: str, win_amount: float, account: str = None):
    """Update the compilation when a bet result is determined"""
    if not telegram_bot or not telegram_chat_id:
        return
    
    try:
        ticket = bet.get('bet_slip_id', 'N/A')
        
        # Update the compilation with the result
        await update_bet_result_in_compilation(account, ticket, result, win_amount)
        logger.info(f"Compilation updated for Ticket#{ticket}: {result}")
        
    except Exception as e:
        logger.error(f"Failed to update result in compilation: {str(e)}")


# Playwright automation service
class Plays888Service:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        
    async def initialize(self):
        try:
            if not self.playwright:
                self.playwright = await async_playwright().start()
            if not self.browser:
                # Launch in headless mode with flags to help with JavaScript execution
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )
            if not self.context:
                # Set a realistic viewport and user agent
                self.context = await self.browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
            if not self.page:
                self.page = await self.context.new_page()
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {str(e)}")
            raise
    
    async def close(self):
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def login(self, username: str, password: str) -> Dict[str, Any]:
        try:
            await self.initialize()
            
            if not self.page:
                return {"success": False, "message": "Failed to initialize browser"}
            
            logger.info(f"Navigating to plays888.co for user {username}")
            await self.page.goto('https://www.plays888.co', timeout=30000)
            
            # Wait for page to load
            await self.page.wait_for_timeout(2000)
            
            # Look for login form
            try:
                # Try to find username/login input
                await self.page.wait_for_selector('input[type="text"], input[name*="user"], input[name*="login"]', timeout=5000)
                await self.page.fill('input[type="text"], input[name*="user"], input[name*="login"]', username)
                
                # Find password input
                await self.page.fill('input[type="password"]', password)
                
                # Look for submit button
                await self.page.click('button[type="submit"], input[type="submit"], button:has-text("Acceder")')
                
                # Wait for navigation or error
                await self.page.wait_for_timeout(3000)
                
                # Check if login was successful
                current_url = self.page.url
                page_content = await self.page.content()
                
                # Basic success check
                if 'error' not in page_content.lower() and 'invalid' not in page_content.lower():
                    logger.info(f"Login successful for {username}")
                    return {"success": True, "message": "Connected to plays888.co"}
                else:
                    return {"success": False, "message": "Login failed - check credentials"}
                    
            except PlaywrightTimeoutError:
                logger.error("Could not find login form")
                return {"success": False, "message": "Could not find login form on website"}
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return {"success": False, "message": f"Login error: {str(e)}"}
    
    async def get_balance(self) -> Optional[float]:
        try:
            # Look for balance element - this would need to be adjusted based on actual website structure
            balance_text = await self.page.locator('text=/balance|saldo/i').first.text_content(timeout=5000)
            # Extract number from text
            import re
            match = re.search(r'\d+\.?\d*', balance_text)
            if match:
                return float(match.group())
        except Exception as e:
            logger.error(f"Error getting balance: {str(e)}")
        return None
    
    async def get_opportunities(self) -> List[Dict[str, Any]]:
        """Scrape available betting opportunities from the website"""
        opportunities = []
        try:
            # This is a mock implementation - actual implementation would scrape the site
            # Navigate to sports betting page
            await self.page.goto('https://www.plays888.co/Deportes.html', timeout=30000)
            await self.page.wait_for_timeout(2000)
            
            # Mock opportunities for demo - American odds
            opportunities = [
                {
                    "event_name": "Team A vs Team B",
                    "odds": +150,  # American odds
                    "sport": "Soccer",
                    "bet_type": "Match Winner"
                },
                {
                    "event_name": "Team C vs Team D",
                    "odds": -110,  # American odds
                    "sport": "Basketball",
                    "bet_type": "Match Winner"
                },
                {
                    "event_name": "Lakers vs Warriors",
                    "odds": +200,  # American odds
                    "sport": "Basketball",
                    "bet_type": "Spread"
                },
            ]
            
        except Exception as e:
            logger.error(f"Error getting opportunities: {str(e)}")
        
        return opportunities
    
    async def place_specific_bet(self, game: str, bet_type: str, line: str, odds: int, wager: float, league: str = "NATIONAL HOCKEY LEAGUE - OT INCLUDED") -> Dict[str, Any]:
        """
        Place a specific bet on plays888.co
        NOTE: User must be connecting from Phoenix, Arizona IP for accurate location
        """
        try:
            if not self.page:
                return {"success": False, "message": "Browser not initialized"}
            
            logger.info(f"Placing bet: {game} - {bet_type} {line} @ {odds} for ${wager}")
            
            # Step 1: Navigate to plays888.co (should already be logged in)
            await self.page.goto('https://www.plays888.co/wager/Welcome.aspx', timeout=30000)
            await self.page.wait_for_load_state('networkidle')
            await self.page.wait_for_timeout(2000)
            
            await self.page.screenshot(path="/tmp/step1_welcome.png")
            logger.info("Step 1: Welcome page loaded")
            
            # Step 2: Click "Straight" in the left sidebar
            try:
                # Look for the Straight link in the sidebar
                await self.page.click('a:has-text("Straight")', timeout=10000)
                await self.page.wait_for_timeout(2000)
                logger.info("Step 2: Clicked 'Straight' in sidebar")
            except Exception as e:
                logger.error(f"Could not find Straight link: {str(e)}")
                return {"success": False, "message": f"Could not find 'Straight' section: {str(e)}"}
            
            await self.page.screenshot(path="/tmp/step2_league_selection.png")
            
            # Step 3: Check the league checkbox and click Continue
            try:
                # Find the checkbox for the specified league
                # The checkbox is next to the league text
                await self.page.click(f'text=/{league}/i', timeout=10000)
                await self.page.wait_for_timeout(1000)
                logger.info(f"Step 3: Checked '{league}' checkbox")
                
                # Click Continue button at bottom - use force to bypass overlays
                await self.page.click('input[value="Continue"]', force=True, timeout=5000)
                logger.info("Clicked Continue, waiting for games to load...")
                
                # CRITICAL: Wait for the games table to actually populate
                # The URL stays the same but content changes via AJAX
                # Wait for the page to finish loading
                await self.page.wait_for_load_state('networkidle', timeout=15000)
                
                # Wait longer and check for game content to appear
                logger.info("Waiting for game data to populate via AJAX...")
                games_loaded = False
                for i in range(15):  # Try up to 15 times (30 seconds)
                    await self.page.wait_for_timeout(2000)
                    
                    # Check multiple indicators that games have loaded
                    button_count = await self.page.locator('input[type="submit"][value*="+"], input[type="submit"][value*="-"]').count()
                    
                    # Also check for team names or game content
                    page_text = await self.page.content()
                    has_game_content = 'vs' in page_text.lower() or 'vrs' in page_text.lower()
                    
                    logger.info(f"Attempt {i+1}: Found {button_count} betting buttons, has_game_content={has_game_content}")
                    
                    if button_count > 10 and has_game_content:  # Games have loaded
                        games_loaded = True
                        logger.info(f"Games loaded successfully! Found {button_count} betting options")
                        break
                
                if not games_loaded:
                    # Take screenshot for debugging
                    await self.page.screenshot(path="/tmp/games_not_loaded.png")
                    return {
                        "success": False,
                        "message": "Games did not load after waiting 30 seconds. Check /tmp/games_not_loaded.png"
                    }
                
                logger.info("Step 3: Games loaded successfully")
            except Exception as e:
                logger.error(f"Could not select league: {str(e)}")
                return {"success": False, "message": f"Could not select league: {str(e)}"}
            
            await self.page.screenshot(path="/tmp/step3_games_list.png")
            
            # Check current URL
            current_url = self.page.url
            logger.info(f"Current URL after Continue: {current_url}")
            
            # Step 4: Find the game and click the odds button
            try:
                # Format odds - need to handle both positive and negative
                # e.g., +110, -125, o150+110
                odds_text = f"+{odds}" if odds > 0 else str(odds)
                
                # Save HTML for debugging
                page_content = await self.page.content()
                with open("/tmp/step3_games_html.html", "w", encoding="utf-8") as f:
                    f.write(page_content)
                logger.info("Saved games page HTML for debugging")
                
                # Find all betting buttons (input type="submit")
                all_inputs = await self.page.query_selector_all('input[type="submit"]')
                logger.info(f"Found {len(all_inputs)} total input buttons on page")
                
                # Look for the specific odds button
                # The odds might be part of a larger string like "o150+110" or just "+110"
                clicked = False
                matched_button = None
                
                for input_elem in all_inputs:
                    try:
                        value = await input_elem.get_attribute('value')
                        # Check if this button contains our odds
                        if value and odds_text in value:
                            matched_button = input_elem
                            logger.info(f"Found matching button with value: {value}")
                            await input_elem.click(force=True)
                            clicked = True
                            logger.info(f"Step 4: Clicked odds button containing '{odds_text}' (full value: {value})")
                            break
                    except Exception as e:
                        logger.error(f"Error checking button: {str(e)}")
                        continue
                
                if not clicked:
                    # Log all button values for debugging
                    logger.error("Could not find matching odds button. Available buttons:")
                    for i, input_elem in enumerate(all_inputs[:20]):  # Log first 20
                        try:
                            value = await input_elem.get_attribute('value')
                            logger.error(f"  Button {i}: {value}")
                        except:
                            pass
                    
                    return {
                        "success": False, 
                        "message": f"Could not find odds button containing '{odds_text}' for game. Found {len(all_inputs)} buttons total. Check /tmp/step3_games_html.html and logs for details."
                    }
                
                # Wait for button selection to register
                await self.page.wait_for_timeout(2000)
                
                # Click Continue button to go to bet slip
                await self.page.click('input[value="Continue"]', force=True, timeout=5000)
                await self.page.wait_for_load_state('networkidle')
                await self.page.wait_for_timeout(2000)
                logger.info("Step 4: Clicked Continue after selecting odds")
                
            except Exception as e:
                logger.error(f"Could not find/click odds: {str(e)}")
                return {"success": False, "message": f"Could not find/click odds: {str(e)}"}
            
            await self.page.screenshot(path="/tmp/step4_betslip.png")
            
            # Step 5: On bet slip page - Select "To Win Amount" and enter amount
            try:
                # Wait for bet slip page to load
                await self.page.wait_for_selector('input[value="To Win Amount"]', timeout=10000)
                logger.info("Bet slip page loaded")
                
                await self.page.screenshot(path="/tmp/step4_betslip.png")
                
                # Select "To Win Amount" radio button
                await self.page.click('input[value="To Win Amount"]', force=True, timeout=5000)
                await self.page.wait_for_timeout(500)
                logger.info("Step 5: Selected 'To Win Amount' radio button")
                
                # Find the text input field for amount and clear it first
                # Look for visible text input (not password, not hidden)
                input_field = await self.page.query_selector('input[type="text"]:not([style*="display: none"]):not([style*="display:none"])')
                if input_field:
                    await input_field.click()
                    await input_field.fill('')  # Clear first
                    await input_field.fill(str(int(wager)))
                    logger.info(f"Step 5: Entered wager amount: ${wager}")
                else:
                    logger.error("Could not find amount input field")
                    return {"success": False, "message": "Could not find amount input field"}
                
                await self.page.wait_for_timeout(1000)
                await self.page.screenshot(path="/tmp/step5_amount_entered.png")
                
                # Click Continue to go to confirmation
                await self.page.click('input[value="Continue"]', force=True, timeout=5000)
                await self.page.wait_for_load_state('networkidle')
                await self.page.wait_for_timeout(2000)
                logger.info("Step 5: Clicked Continue, going to confirmation")
                
            except Exception as e:
                logger.error(f"Could not enter wager amount: {str(e)}")
                return {"success": False, "message": f"Could not enter wager amount: {str(e)}"}
            
            await self.page.screenshot(path="/tmp/step5_confirmation.png")
            
            # Step 6: On confirmation page - Click Confirm button to place bet
            try:
                # Wait for confirmation page to load
                await self.page.wait_for_selector('input[value="Confirm"]', timeout=10000)
                logger.info("Confirmation page loaded")
                
                await self.page.screenshot(path="/tmp/step5_confirmation_page.png")
                
                # Click Confirm to place the bet
                await self.page.click('input[value="Confirm"]', force=True, timeout=5000)
                await self.page.wait_for_load_state('networkidle')
                await self.page.wait_for_timeout(3000)
                logger.info("Step 6: Clicked Confirm button - bet should be placed!")
                
            except Exception as e:
                logger.error(f"Could not click Confirm: {str(e)}")
                await self.page.screenshot(path="/tmp/confirm_error.png")
                return {"success": False, "message": f"Could not click Confirm: {str(e)}"}
            
            await self.page.screenshot(path="/tmp/step6_success_page.png")
            
            # Step 7: Verify bet was placed by checking for Ticket# on success page
            try:
                # Check if we're on the ConfirmWager.aspx success page
                current_url = self.page.url
                logger.info(f"Final URL: {current_url}")
                
                # Look for "Ticket#" text on the page
                page_content = await self.page.content()
                with open("/tmp/success_page.html", "w", encoding="utf-8") as f:
                    f.write(page_content)
                
                # Extract ticket number
                import re
                ticket_match = re.search(r'Ticket#?[:\s]*(\d+)', page_content, re.IGNORECASE)
                
                if ticket_match or "ConfirmWager" in current_url:
                    ticket_number = ticket_match.group(1) if ticket_match else "Check screenshot"
                    
                    logger.info(f"🎉 BET PLACED SUCCESSFULLY! Ticket#: {ticket_number}")
                    
                    return {
                        "success": True,
                        "message": f"✅ Bet placed successfully: {game} - {bet_type} {line} @ {odds} for ${wager} MXN",
                        "ticket_number": ticket_number,
                        "bet_details": {
                            "game": game,
                            "bet_type": bet_type,
                            "line": line,
                            "odds": odds,
                            "wager": wager,
                            "league": league
                        },
                        "verification": "Check /tmp/step6_success_page.png for visual confirmation"
                    }
                else:
                    logger.error("Could not verify bet placement")
                    return {
                        "success": False,
                        "message": "Reached final page but could not verify bet placement (no Ticket# found)",
                        "current_url": current_url,
                        "screenshots": "Check /tmp/step*.png and /tmp/success_page.html for debugging"
                    }
                    
            except Exception as e:
                logger.error(f"Error verifying bet: {str(e)}")
                return {"success": False, "message": f"Error verifying bet: {str(e)}"}
                
        except Exception as e:
            logger.error(f"Error placing bet: {str(e)}")
            await self.page.screenshot(path="/tmp/error.png")
            return {"success": False, "message": f"Error: {str(e)}", "screenshot": "/tmp/error.png"}


plays888_service = Plays888Service()

# Bet monitoring scheduler
scheduler = AsyncIOScheduler()
monitoring_enabled = False

# Random interval settings (in minutes)
MIN_INTERVAL = 7
MAX_INTERVAL = 15

# Track last check time for watchdog
last_check_time = None

async def save_next_check_time(next_time):
    """Save next scheduled check time to database for persistence across restarts"""
    try:
        await db.monitor_state.update_one(
            {"type": "next_check"},
            {"$set": {"next_check_time": next_time, "updated_at": datetime.now(timezone.utc)}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Failed to save next check time: {e}")

async def get_next_check_time():
    """Get next scheduled check time from database"""
    try:
        state = await db.monitor_state.find_one({"type": "next_check"}, {"_id": 0})
        if state:
            return state.get("next_check_time")
    except Exception as e:
        logger.error(f"Failed to get next check time: {e}")
    return None

def schedule_next_check():
    """DEPRECATED - Now using monitoring_loop() instead"""
    # Do nothing - monitoring is handled by the background loop
    pass

async def monitor_and_reschedule():
    """Run monitoring - called by manual check API"""
    await run_monitoring_cycle()


async def send_check_notification(check_time, new_bets_found):
    """Send a notification to Telegram that a check was performed - auto-deletes after 30 min"""
    try:
        telegram_config = await db.telegram_config.find_one({}, {"_id": 0})
        if not telegram_config or not telegram_config.get("bot_token"):
            return
        
        bot = Bot(token=telegram_config["bot_token"])
        chat_id = telegram_config["chat_id"]
        
        # Generate random next interval for display
        next_interval = random.randint(MIN_INTERVAL, MAX_INTERVAL)
        
        # Build message - handle None safely
        if new_bets_found is None:
            new_bets_found = {}
        enano_new = new_bets_found.get("jac075", 0) or 0
        tipster_new = new_bets_found.get("jac083", 0) or 0
        
        if enano_new > 0 or tipster_new > 0:
            status = f"🆕 New bets: ENANO={enano_new}, TIPSTER={tipster_new}"
        else:
            status = "✅ No new bets"
        
        message = f"""🔄 *CHECK COMPLETE*
⏰ {check_time.strftime('%I:%M %p')} Arizona
{status}
⏭️ Next check in ~{next_interval} min"""
        
        sent_msg = await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"Check notification sent to Telegram")
        
        # Schedule auto-deletion after 30 minutes
        asyncio.create_task(delete_message_later(bot, chat_id, sent_msg.message_id, 30))
        
    except Exception as e:
        logger.error(f"Failed to send check notification: {str(e)}")


async def watchdog_check():
    """Watchdog to ensure monitoring is running - runs every 5 minutes"""
    global last_check_time, monitoring_enabled
    
    if not monitoring_enabled:
        return
    
    # Check if we're in sleep hours
    from zoneinfo import ZoneInfo
    arizona_tz = ZoneInfo('America/Phoenix')
    now_arizona = datetime.now(arizona_tz)
    current_hour = now_arizona.hour
    current_minute = now_arizona.minute
    current_time_minutes = current_hour * 60 + current_minute
    
    sleep_start = 22 * 60 + 45  # 10:45 PM
    sleep_end = 6 * 60 + 0      # 6:00 AM
    
    if current_time_minutes >= sleep_start or current_time_minutes < sleep_end:
        return  # Don't check during sleep hours
    
    # Check if last check was more than 20 minutes ago
    if last_check_time:
        minutes_since_last = (datetime.now(timezone.utc) - last_check_time).total_seconds() / 60
        
        if minutes_since_last > 20:
            logger.warning(f"Watchdog: No check for {minutes_since_last:.0f} minutes! Triggering immediate check...")
            
            # Re-schedule monitoring
            schedule_next_check()
            
            # Trigger immediate check
            asyncio.create_task(monitor_and_reschedule())
    else:
        # First watchdog run, initialize last_check_time
        last_check_time = datetime.now(timezone.utc)


async def monitor_open_bets():
    """Background job to monitor plays888.co for new bets"""
    global monitoring_enabled
    
    new_bets_count = {"jac075": 0, "jac083": 0}
    
    if not monitoring_enabled:
        return new_bets_count
    
    # Check if we're in sleep hours (10:45 PM - 6:00 AM Arizona time)
    # Arizona is UTC-7 (no daylight saving)
    from zoneinfo import ZoneInfo
    arizona_tz = ZoneInfo('America/Phoenix')
    now_arizona = datetime.now(arizona_tz)
    current_hour = now_arizona.hour
    current_minute = now_arizona.minute
    current_time_minutes = current_hour * 60 + current_minute
    
    # Sleep window: 10:45 PM (22:45 = 1365 mins) to 6:00 AM (6:00 = 360 mins)
    sleep_start = 22 * 60 + 45  # 10:45 PM = 1365 minutes
    sleep_end = 6 * 60 + 0       # 6:00 AM = 330 minutes
    
    if current_time_minutes >= sleep_start or current_time_minutes < sleep_end:
        logger.info(f"Sleep hours ({now_arizona.strftime('%I:%M %p')} Arizona) - skipping bet check")
        return new_bets_count
    
    logger.info(f"Checking plays888.co for new bets... ({now_arizona.strftime('%I:%M %p')} Arizona)")
    
    try:
        # Get ALL active connections (multiple accounts)
        connections = await db.connections.find({"is_connected": True}, {"_id": 0}).to_list(100)
        
        if not connections:
            logger.info("No active connections, skipping bet monitoring")
            return new_bets_count
        
        # Monitor each account
        for conn in connections:
            new_count = await monitor_single_account(conn)
            username = conn.get("username", "")
            new_bets_count[username] = new_count
            
    except Exception as e:
        logger.error(f"Error in bet monitoring: {str(e)}")
    
    return new_bets_count

async def monitor_single_account(conn: dict):
    """Monitor a single account for new bets - returns count of new bets found"""
    username = conn["username"]
    password = decrypt_password(conn["password_encrypted"])
    new_bets_count = 0
    
    logger.info(f"Monitoring account: {username}")
    monitor_service = None
    
    try:
        # Create a new service instance for monitoring
        monitor_service = Plays888Service()
        await monitor_service.initialize()
        
        # Login
        login_result = await monitor_service.login(username, password)
        if not login_result["success"]:
            logger.error(f"Monitor login failed for {username}: {login_result['message']}")
            await monitor_service.close()
            return new_bets_count  # Return 0, not None
        
        # Navigate to Open Bets page
        await monitor_service.page.goto('https://www.plays888.co/wager/OpenBets.aspx', timeout=30000)
        await monitor_service.page.wait_for_timeout(5000)  # Wait longer for table to load
        
        # Extract open bets by parsing the table rows using Playwright
        import re
        
        # Try to extract bet data from table rows
        bets_data = await monitor_service.page.evaluate('''() => {
            const bets = [];
            // Find all table rows in the bets table
            const rows = document.querySelectorAll('table tr');
            
            for (let i = 0; i < rows.length; i++) {
                const row = rows[i];
                const cells = row.querySelectorAll('td');
                
                // Table structure based on plays888.co:
                // 0: GameDate (contains Ticket#)
                // 1: User/Phone
                // 2: Date Placed
                // 3: Sport (CBB, NBA, NHL, SOC, etc)
                // 4: Description (bet details, game name)
                // 5: Risk/Win amounts
                
                if (cells.length >= 5) {
                    // Extract ticket number from first column
                    const ticketCell = cells[0].textContent || '';
                    const ticketMatch = ticketCell.match(/Ticket#?[:\\s-]*(\\d+)/i);
                    
                    if (ticketMatch) {
                        const ticket = ticketMatch[1];
                        
                        // Column indices - adjusted based on actual table structure
                        const sport = cells[3] ? cells[3].textContent.trim() : '';
                        const description = cells[4] ? cells[4].textContent.trim() : '';
                        const riskWin = cells[5] ? cells[5].textContent.trim() : '';
                        
                        // Parse risk/win amounts (format: "1100.00 / 1000.00" or "500.00 / 9500.00")
                        let wager = 0;
                        let toWin = 0;
                        const riskMatch = riskWin.match(/([\\d,]+\\.?\\d*)\\s*\\/\\s*([\\d,]+\\.?\\d*)/);
                        if (riskMatch) {
                            wager = parseFloat(riskMatch[1].replace(/,/g, ''));
                            toWin = parseFloat(riskMatch[2].replace(/,/g, ''));
                        }
                        
                        // Calculate American odds from Risk/Win amounts
                        // This works for ALL bet types (Straight, Parlay, Teaser, etc.)
                        let odds = 0;
                        if (wager > 0 && toWin > 0) {
                            if (toWin >= wager) {
                                // Positive odds: (Win / Risk) * 100
                                odds = Math.round((toWin / wager) * 100);
                            } else {
                                // Negative odds: -(Risk / Win) * 100
                                odds = Math.round(-(wager / toWin) * 100);
                            }
                        }
                        
                        // Better parsing of the description field
                        // Description format examples:
                        // "STRAIGHT BET[2526] MILWAUKEE BUCKS 2H +1½-110"
                        // "STRAIGHT BET[297497888] Dallas Mavericks..."
                        // "PARLAY[123] Team A vs Team B..."
                        
                        let game = '';
                        let betType = '';
                        
                        // First, extract game name from parentheses (TEAM A vs TEAM B)
                        const vsMatch = description.match(/\\(([^)]*(?:vs|vrs)[^)]*)\\)/i);
                        if (vsMatch) {
                            game = vsMatch[1].trim();
                        }
                        
                        // Check bet type
                        if (description.toUpperCase().includes('PARLAY')) {
                            betType = 'PARLAY';
                        } else if (description.toUpperCase().includes('TEASER')) {
                            betType = 'TEASER';
                        } else {
                            // Look for TOTAL over/under
                            const totalMatch = description.match(/TOTAL\\s+([ou][\\d.½]+)/i);
                            if (totalMatch) {
                                betType = 'TOTAL ' + totalMatch[1].toUpperCase();
                            }
                            
                            // Look for spread like "+1½" or "-5.5" with team name
                            // Format after bracket: "TEAM NAME +/-SPREAD"
                            const afterBracket = description.match(/\\]\\s*(.+)/);
                            if (afterBracket) {
                                const betDetails = afterBracket[1].trim();
                                
                                // Extract team name and spread/line
                                // Pattern: "TEAM NAME +/-NUMBER" or "TEAM NAME 2H +/-NUMBER"
                                const teamSpreadMatch = betDetails.match(/^([A-Za-z][A-Za-z0-9\\s\\.]+?)\\s*(2H\\s*)?([+-][\\d½\\.]+)/);
                                if (teamSpreadMatch) {
                                    const teamName = teamSpreadMatch[1].trim();
                                    const halfIndicator = teamSpreadMatch[2] ? '2H ' : '';
                                    const spread = teamSpreadMatch[3];
                                    
                                    if (!betType) {
                                        betType = teamName + ' ' + halfIndicator + spread;
                                    }
                                    if (!game) {
                                        game = teamName;
                                    }
                                }
                                
                                // If still no game, use the bet details directly (cleaned up)
                                if (!game && betDetails) {
                                    // Remove odds from end like "-110" and clean up
                                    game = betDetails.replace(/[+-]\\d{3}$/, '').trim();
                                    // Limit length
                                    if (game.length > 50) {
                                        game = game.substring(0, 47) + '...';
                                    }
                                }
                            }
                        }
                        
                        // Fallback: if still no info, use cleaned description
                        if (!game) {
                            // Remove "STRAIGHT BET", IDs, etc and get the actual content
                            let cleanDesc = description
                                .replace(/STRAIGHT\\s*BET/gi, '')
                                .replace(/\\[[^\\]]+\\]/g, '')  // Remove [ID]
                                .replace(/[+-]\\d{3}$/g, '')   // Remove trailing odds
                                .trim();
                            if (cleanDesc.length > 50) {
                                cleanDesc = cleanDesc.substring(0, 47) + '...';
                            }
                            game = cleanDesc || 'Unknown';
                        }
                        
                        if (!betType) {
                            betType = 'Straight';
                        }
                        
                        bets.push({
                            ticket: ticket,
                            description: description,
                            sport: sport,
                            game: game,
                            betType: betType,
                            odds: odds,
                            wager: wager,
                            toWin: toWin
                        });
                    }
                }
            }
            return bets;
        }''')
        
        logger.info(f"Extracted {len(bets_data)} open bets from plays888.co table")
        
        # Check each bet against our database
        for bet_info in bets_data:
            ticket_num = bet_info.get('ticket', '')
            
            if not ticket_num:
                continue
                
            # Check if this ticket already exists in our database
            existing_bet = await db.bet_history.find_one({"bet_slip_id": ticket_num})
            
            if not existing_bet:
                # New bet detected! 
                logger.info(f"New bet detected: Ticket#{ticket_num}")
                logger.info(f"Bet details: {bet_info}")
                
                game = bet_info.get('game', '') or 'Unknown Game'
                bet_type = bet_info.get('betType', '') or 'Unknown'
                odds = bet_info.get('odds', -110)
                wager = bet_info.get('wager', 0)
                to_win = bet_info.get('toWin', 0)
                sport = bet_info.get('sport', '')
                description = bet_info.get('description', '')
                
                # If game is still unknown, use part of description
                if game == 'Unknown Game' and description:
                    # Try to extract game from description
                    game = description[:50] + '...' if len(description) > 50 else description
                
                # Store in database with account info for filtering
                bet_doc = {
                    "id": str(uuid.uuid4()),
                    "opportunity_id": "mobile_detected",
                    "rule_id": "mobile_detected",
                    "wager_amount": wager,
                    "odds": odds,
                    "status": "placed",
                    "placed_at": datetime.now(timezone.utc).isoformat(),
                    "result": None,
                    "game": game,
                    "bet_type": bet_type,
                    "line": bet_type,
                    "bet_slip_id": ticket_num,
                    "account": username,
                    "notes": f"Account: {username}. Auto-detected from plays888.co. Sport: {sport}"
                }
                await db.bet_history.insert_one(bet_doc)
                
                # Send Telegram notification with actual details
                await send_telegram_notification({
                    "game": game,
                    "bet_type": bet_type,
                    "line": bet_type,
                    "odds": odds,
                    "wager": wager,
                    "potential_win": to_win,
                    "ticket_number": ticket_num,
                    "status": "Placed",
                    "league": f"{sport} - Detected from mobile/web"
                }, account=username)
                new_bets_count += 1
        
        await monitor_service.close()
        logger.info(f"Bet monitoring check complete for {username}")
        return new_bets_count
        
    except Exception as e:
        logger.error(f"Error monitoring account {username}: {str(e)}")
        if monitor_service:
            try:
                await monitor_service.close()
            except:
                pass
        return new_bets_count


# API Routes
@api_router.get("/")
async def root():
    return {"message": "Betting Automation API", "status": "running"}


@api_router.post("/connection/setup")
async def setup_connection(connection: ConnectionCreate):
    """Setup connection credentials for plays888.co"""
    try:
        # Encrypt password
        encrypted_password = encrypt_password(connection.password)
        
        # Test connection
        login_result = await plays888_service.login(connection.username, connection.password)
        
        # Store in database
        conn_doc = {
            "id": str(uuid.uuid4()),
            "username": connection.username,
            "password_encrypted": encrypted_password,
            "website": "plays888.co",
            "is_connected": login_result["success"],
            "last_connection": datetime.now(timezone.utc).isoformat() if login_result["success"] else None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Delete existing connections for this user
        await db.connections.delete_many({"username": connection.username})
        
        # Insert new connection
        await db.connections.insert_one(conn_doc)
        
        # Close browser after test
        await plays888_service.close()
        
        return {"success": login_result["success"], "message": login_result["message"]}
        
    except Exception as e:
        logger.error(f"Setup connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/connection/status")
async def get_connection_status():
    """Get current connection status"""
    try:
        conn = await db.connections.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
        
        if not conn:
            return AccountStatus(is_connected=False)
        
        return AccountStatus(
            is_connected=conn.get("is_connected", False),
            username=conn.get("username"),
            last_sync=datetime.fromisoformat(conn["last_connection"]) if conn.get("last_connection") else None
        )
    except Exception as e:
        logger.error(f"Get connection status error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/rules")
async def create_rule(rule: BettingRuleCreate):
    """Create a new betting rule"""
    try:
        rule_doc = {
            "id": str(uuid.uuid4()),
            "name": rule.name,
            "enabled": rule.enabled,
            "min_odds": rule.min_odds,
            "max_odds": rule.max_odds,
            "wager_amount": rule.wager_amount,
            "auto_place": rule.auto_place,
            "sport": rule.sport,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.betting_rules.insert_one(rule_doc)
        return {"success": True, "rule_id": rule_doc["id"]}
    except Exception as e:
        logger.error(f"Create rule error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/rules")
async def get_rules():
    """Get all betting rules"""
    try:
        rules = await db.betting_rules.find({}, {"_id": 0}).to_list(100)
        
        for rule in rules:
            if isinstance(rule.get('created_at'), str):
                rule['created_at'] = datetime.fromisoformat(rule['created_at'])
        
        return rules
    except Exception as e:
        logger.error(f"Get rules error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """Delete a betting rule"""
    try:
        result = await db.betting_rules.delete_one({"id": rule_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Rule not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete rule error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/opportunities")
async def get_opportunities():
    """Get current betting opportunities that match rules"""
    try:
        # Get connection
        conn = await db.connections.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
        
        if not conn or not conn.get("is_connected"):
            return {"opportunities": [], "message": "Not connected to plays888.co"}
        
        # Get active rules
        rules = await db.betting_rules.find({"enabled": True}, {"_id": 0}).to_list(100)
        
        if not rules:
            return {"opportunities": [], "message": "No active betting rules"}
        
        # Login and get opportunities
        username = conn["username"]
        password = decrypt_password(conn["password_encrypted"])
        
        await plays888_service.login(username, password)
        raw_opportunities = await plays888_service.get_opportunities()
        await plays888_service.close()
        
        # Match opportunities with rules
        matched_opportunities = []
        for opp in raw_opportunities:
            for rule in rules:
                # Check if opportunity matches rule
                matches = True
                if rule.get("min_odds") and opp["odds"] < rule["min_odds"]:
                    matches = False
                if rule.get("max_odds") and opp["odds"] > rule["max_odds"]:
                    matches = False
                if rule.get("sport") and opp["sport"].lower() != rule["sport"].lower():
                    matches = False
                
                if matches:
                    potential_win = calculate_american_odds_payout(rule["wager_amount"], opp["odds"])
                    opp_doc = {
                        "id": str(uuid.uuid4()),
                        "event_name": opp["event_name"],
                        "odds": opp["odds"],
                        "sport": opp["sport"],
                        "bet_type": opp["bet_type"],
                        "available": True,
                        "matched_rule_id": rule["id"],
                        "matched_rule_name": rule["name"],
                        "wager_amount": rule["wager_amount"],
                        "potential_win": potential_win,
                        "auto_place": rule["auto_place"],
                        "discovered_at": datetime.now(timezone.utc).isoformat()
                    }
                    matched_opportunities.append(opp_doc)
                    break
        
        return {"opportunities": matched_opportunities}
    except Exception as e:
        logger.error(f"Get opportunities error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/bets/place")
async def place_bet(bet_request: PlaceBetRequest):
    """Place a bet manually"""
    try:
        # Get opportunity from recent scan
        # In production, this would place actual bet via Playwright
        
        bet_doc = {
            "id": str(uuid.uuid4()),
            "opportunity_id": bet_request.opportunity_id,
            "rule_id": "manual",
            "wager_amount": bet_request.wager_amount,
            "odds": 0,
            "status": "placed",
            "placed_at": datetime.now(timezone.utc).isoformat(),
            "result": None
        }
        
        await db.bet_history.insert_one(bet_doc)
        
        return {"success": True, "message": "Bet placed successfully", "bet_id": bet_doc["id"]}
    except Exception as e:
        logger.error(f"Place bet error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class SpecificBetRequest(BaseModel):
    game: str
    bet_type: str
    line: str
    odds: int
    wager: float
    league: str = "NATIONAL HOCKEY LEAGUE - OT INCLUDED"  # Default to NHL

class ManualBetRecord(BaseModel):
    game: str
    bet_type: str
    line: str
    odds: int
    wager: float
    bet_slip_id: Optional[str] = None
    notes: Optional[str] = None


@api_router.post("/bets/place-specific")
async def place_specific_bet(bet_request: SpecificBetRequest):
    """Place a specific bet on plays888.co"""
    # Create a new service instance for this bet
    bet_service = Plays888Service()
    
    try:
        # Get connection credentials
        conn = await db.connections.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
        
        if not conn or not conn.get("is_connected"):
            raise HTTPException(status_code=400, detail="Not connected to plays888.co")
        
        # Login and place bet
        username = conn["username"]
        password = decrypt_password(conn["password_encrypted"])
        
        await bet_service.initialize()
        login_result = await bet_service.login(username, password)
        
        if not login_result["success"]:
            await bet_service.close()
            raise HTTPException(status_code=400, detail=f"Login failed: {login_result['message']}")
        
        # Place the bet
        result = await bet_service.place_specific_bet(
            game=bet_request.game,
            bet_type=bet_request.bet_type,
            line=bet_request.line,
            odds=bet_request.odds,
            wager=bet_request.wager,
            league=bet_request.league
        )
        
        await bet_service.close()
        
        # Store in history
        if result["success"]:
            bet_doc = {
                "id": str(uuid.uuid4()),
                "opportunity_id": "specific",
                "rule_id": "manual",
                "wager_amount": bet_request.wager,
                "odds": bet_request.odds,
                "status": "placed",
                "placed_at": datetime.now(timezone.utc).isoformat(),
                "result": None,
                "game": bet_request.game,
                "bet_type": bet_request.bet_type,
                "line": bet_request.line
            }
            await db.bet_history.insert_one(bet_doc)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Place specific bet error: {str(e)}")
        await bet_service.close()
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/bets/history")
async def get_bet_history():
    """Get betting history"""
    try:
        bets = await db.bet_history.find({}, {"_id": 0}).sort("placed_at", -1).to_list(100)
        
        for bet in bets:
            if isinstance(bet.get('placed_at'), str):
                bet['placed_at'] = datetime.fromisoformat(bet['placed_at'])
        
        return bets
    except Exception as e:
        logger.error(f"Get bet history error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/bets/record-manual")
async def record_manual_bet(bet: ManualBetRecord):
    """Record a manually placed bet"""
    try:
        potential_win = calculate_american_odds_payout(bet.wager, bet.odds)
        
        bet_doc = {
            "id": str(uuid.uuid4()),
            "opportunity_id": "manual",
            "rule_id": "manual",
            "wager_amount": bet.wager,
            "odds": bet.odds,
            "status": "placed",
            "placed_at": datetime.now(timezone.utc).isoformat(),
            "result": None,
            "game": bet.game,
            "bet_type": bet.bet_type,
            "line": bet.line,
            "bet_slip_id": bet.bet_slip_id,
            "notes": bet.notes
        }
        
        await db.bet_history.insert_one(bet_doc)
        
        # Send Telegram notification
        await send_telegram_notification({
            "game": bet.game,
            "bet_type": bet.bet_type,
            "line": bet.line,
            "odds": bet.odds,
            "wager": bet.wager,
            "potential_win": potential_win,
            "ticket_number": bet.bet_slip_id or bet_doc["id"],
            "status": "Placed",
            "league": bet.notes if "via extension" not in (bet.notes or "") else ""
        })
        
        return {
            "success": True,
            "message": f"Bet recorded: {bet.game} - {bet.bet_type} {bet.line} @ {bet.odds} for ${bet.wager}",
            "bet_id": bet_doc["id"]
        }
    except Exception as e:
        logger.error(f"Record manual bet error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: int

@api_router.post("/telegram/config")
async def configure_telegram(config: TelegramConfig):
    """Configure Telegram bot for notifications"""
    global telegram_bot, telegram_chat_id
    
    try:
        # Test the bot token
        test_bot = Bot(token=config.bot_token)
        bot_info = await test_bot.get_me()
        
        # Store configuration in memory
        telegram_bot = test_bot
        telegram_chat_id = config.chat_id
        
        # Persist to MongoDB (upsert - update or insert)
        await db.telegram_config.delete_many({})  # Remove old config
        await db.telegram_config.insert_one({
            "bot_token": config.bot_token,
            "chat_id": config.chat_id,
            "bot_username": bot_info.username,
            "bot_name": bot_info.first_name,
            "configured_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Telegram config saved to database for @{bot_info.username}")
        
        # Send test message
        await telegram_bot.send_message(
            chat_id=telegram_chat_id,
            text="✅ *Telegram Notifications Enabled*\\n\\nYou will receive notifications when bets are placed\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
        return {
            "success": True,
            "message": f"Telegram configured successfully. Bot: @{bot_info.username}",
            "bot_name": bot_info.first_name
        }
    except Exception as e:
        logger.error(f"Telegram configuration error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to configure Telegram: {str(e)}")

@api_router.get("/telegram/status")
async def telegram_status():
    """Check Telegram configuration status"""
    global telegram_bot, telegram_chat_id
    
    # If not in memory, try loading from database
    if not telegram_bot or not telegram_chat_id:
        try:
            config = await db.telegram_config.find_one({}, {"_id": 0})
            if config:
                telegram_bot = Bot(token=config["bot_token"])
                telegram_chat_id = int(config["chat_id"])
                logger.info("Telegram reloaded from database")
        except Exception as e:
            logger.error(f"Error loading Telegram from database: {e}")
    
    if telegram_bot and telegram_chat_id:
        try:
            bot_info = await telegram_bot.get_me()
            return {
                "configured": True,
                "bot_username": bot_info.username,
                "bot_name": bot_info.first_name,
                "chat_id": telegram_chat_id
            }
        except:
            return {"configured": False, "error": "Bot token invalid"}
    return {"configured": False}

@api_router.post("/telegram/test")
async def test_telegram():
    """Send a test notification using the new compilation system"""
    if not telegram_bot or not telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured")
    
    try:
        # Test the new compilation-based notification
        await send_telegram_notification({
            "game": "FALCONS vs CARDINALS",
            "description": "Atlanta Falcons @ Arizona Cardinals",
            "bet_type": "TOTAL UNDER 48",
            "line": "u48",
            "odds": -110,
            "wager": 2200,
            "potential_win": 2000,
            "ticket_number": f"TEST{datetime.now().strftime('%H%M%S')}",
            "status": "Placed"
        }, account="jac075")  # Test with ENANO label
        return {"success": True, "message": "Test bet added to compilation"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/telegram/test-compilation")
async def test_compilation():
    """Test the full compilation workflow with multiple bets"""
    if not telegram_bot or not telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured")
    
    try:
        import time
        timestamp = int(time.time())
        
        # Add first bet
        await send_telegram_notification({
            "game": "FALCONS vs CARDINALS",
            "description": "Atlanta Falcons @ Arizona Cardinals",
            "bet_type": "TOTAL UNDER 48",
            "odds": -110,
            "wager": 2200,
            "potential_win": 2000,
            "ticket_number": f"DEMO{timestamp}A"
        }, account="jac075")
        
        await asyncio.sleep(2)
        
        # Add second bet
        await send_telegram_notification({
            "game": "JAGUARS vs BRONCOS",
            "description": "Jacksonville Jaguars @ Denver Broncos",
            "bet_type": "TOTAL OVER 47",
            "odds": -110,
            "wager": 2200,
            "potential_win": 2000,
            "ticket_number": f"DEMO{timestamp}B"
        }, account="jac075")
        
        await asyncio.sleep(2)
        
        # Mark first bet as won
        await update_bet_result_in_compilation("jac075", f"DEMO{timestamp}A", "won", 2000)
        
        return {"success": True, "message": "Test compilation workflow completed - check Telegram!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/telegram/daily-summary")
async def trigger_daily_summary():
    """Manually trigger the daily betting summary"""
    if not telegram_bot or not telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured")
    
    try:
        await send_daily_summary()
        return {"success": True, "message": "Daily summary sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/telegram/send-compilations")
async def send_all_compilations():
    """Send/update compilation messages for all accounts with bets today"""
    if not telegram_bot or not telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured")
    
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        today = datetime.now(arizona_tz).strftime('%Y-%m-%d')
        
        # Find all compilations for today
        compilations = await db.daily_compilations.find({"date": today}).to_list(10)
        
        sent_count = 0
        for comp in compilations:
            account = comp.get('account')
            if account:
                await update_compilation_message(account)
                sent_count += 1
        
        return {"success": True, "message": f"Sent {sent_count} compilation messages"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/telegram/activity-summary")
async def trigger_activity_summary():
    """Manually trigger the activity summary"""
    if not telegram_bot or not telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured")
    
    try:
        await send_activity_summary()
        return {"success": True, "message": "Activity summary sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/bets/check-results")
async def trigger_results_check():
    """Manually trigger a check for settled bet results"""
    try:
        await check_bet_results()
        return {"success": True, "message": "Results check completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/stats")
async def get_stats():
    """Get statistics for dashboard"""
    try:
        total_bets = await db.bet_history.count_documents({})
        active_rules = await db.betting_rules.count_documents({"enabled": True})
        
        return {
            "total_bets": total_bets,
            "active_rules": active_rules,
            "win_rate": 0,
            "total_profit": 0
        }
    except Exception as e:
        logger.error(f"Get stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/accounts")
async def get_accounts():
    """Get list of connected accounts"""
    try:
        connections = await db.connections.find({"is_connected": True}, {"_id": 0}).to_list(100)
        accounts = []
        for conn in connections:
            username = conn.get("username", "")
            label = ACCOUNT_LABELS.get(username, username)
            accounts.append({
                "username": username,
                "label": label,
                "is_connected": conn.get("is_connected", False)
            })
        return {"accounts": accounts}
    except Exception as e:
        logger.error(f"Get accounts error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Cache for account summaries (5-minute TTL)
account_summary_cache = {}
CACHE_TTL_SECONDS = 300  # 5 minutes

@api_router.get("/accounts/{username}/summary")
async def get_account_summary(username: str, force_refresh: bool = False):
    """Get daily/weekly profit summary for a specific account (cached for 5 min)"""
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        now_arizona = datetime.now(arizona_tz)
        current_time = datetime.now(timezone.utc)
        
        # Check cache (unless force refresh requested)
        if not force_refresh and username in account_summary_cache:
            cached = account_summary_cache[username]
            cache_age = (current_time - cached['cached_at']).total_seconds()
            if cache_age < CACHE_TTL_SECONDS:
                logger.info(f"Returning cached summary for {username} (age: {cache_age:.0f}s)")
                return cached['data']
        
        # Find the connection
        conn = await db.connections.find_one({"username": username, "is_connected": True}, {"_id": 0})
        if not conn:
            raise HTTPException(status_code=404, detail=f"Account {username} not found or not connected")
        
        password = decrypt_password(conn["password_encrypted"])
        label = ACCOUNT_LABELS.get(username, username)
        
        # Get the daily totals from plays888
        totals = await get_plays888_daily_totals(username, password)
        
        day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        today_day = day_names[now_arizona.weekday()]
        
        # Get bet count from the scraped data (from plays888.co)
        total_bets = totals.get('total_bets', 0) if totals else 0
        
        if not totals or not totals.get('daily_profits'):
            result = {
                "username": username,
                "label": label,
                "success": False,
                "error": "Could not retrieve data from plays888.co",
                "daily_profits": [],
                "week_total": 0,
                "today_profit": 0,
                "today_day": today_day,
                "date": now_arizona.strftime('%B %d, %Y'),
                "total_bets": total_bets
            }
        else:
            # Find today's profit
            today_profit = 0
            for day_data in totals['daily_profits']:
                if day_data['day'].lower() == today_day:
                    today_profit = day_data['profit']
                    break
            
            result = {
                "username": username,
                "label": label,
                "success": True,
                "daily_profits": totals['daily_profits'],
                "week_total": totals.get('week_total', 0),
                "today_profit": today_profit,
                "today_day": today_day,
                "date": now_arizona.strftime('%B %d, %Y'),
                "total_bets": total_bets
            }
        
        # Store in cache
        account_summary_cache[username] = {
            'data': result,
            'cached_at': current_time
        }
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get account summary error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/accounts/all/summaries")
async def get_all_account_summaries():
    """Get summaries for all connected accounts (uses cache)"""
    try:
        connections = await db.connections.find({"is_connected": True}, {"_id": 0}).to_list(100)
        summaries = []
        
        for conn in connections:
            username = conn.get("username", "")
            try:
                # Use the cached endpoint logic
                summary = await get_account_summary(username, force_refresh=False)
                summaries.append(summary)
            except Exception as e:
                logger.error(f"Error getting summary for {username}: {e}")
                summaries.append({
                    "username": username,
                    "label": ACCOUNT_LABELS.get(username, username),
                    "success": False,
                    "error": str(e)
                })
        
        return {"summaries": summaries}
    except Exception as e:
        logger.error(f"Get all summaries error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/monitoring/start")
async def start_monitoring():
    """Start the bet monitoring system"""
    global monitoring_enabled
    
    # Check if connection is configured
    conn = await db.connections.find_one({}, {"_id": 0})
    if not conn or not conn.get("is_connected"):
        raise HTTPException(status_code=400, detail="Please configure plays888.co connection first")
    
    monitoring_enabled = True
    
    # Save monitoring config to DB for auto-start on restart
    await db.monitor_config.delete_many({})
    await db.monitor_config.insert_one({
        "auto_start": True,
        "interval_minutes": 15,  # Production interval
        "enabled_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Schedule the job with random intervals (7-15 minutes)
    # Uses a wrapper that reschedules with random delay after each run
    schedule_next_check()
    
    if not scheduler.running:
        scheduler.start()
    
    logger.info("Bet monitoring started - checking every 7-15 minutes randomly (paused 10:45 PM - 6:00 AM Arizona)")
    
    return {
        "success": True,
        "message": "Bet monitoring started. Will check plays888.co every 7-15 minutes randomly (paused during sleep hours 10:45 PM - 6:00 AM Arizona).",
        "interval": "7-15 minutes (random)"
    }

@api_router.post("/monitoring/stop")
async def stop_monitoring():
    """Stop the bet monitoring system"""
    global monitoring_enabled
    
    monitoring_enabled = False
    
    # Update DB to disable auto-start
    await db.monitor_config.update_one(
        {},
        {"$set": {"auto_start": False}},
        upsert=True
    )
    
    if scheduler.running:
        scheduler.remove_job('bet_monitor')
    
    logger.info("Bet monitoring stopped")
    
    return {
        "success": True,
        "message": "Bet monitoring stopped"
    }

@api_router.get("/monitoring/status")
async def monitoring_status():
    """Get monitoring system status"""
    next_check = None
    try:
        if monitoring_enabled and scheduler.running:
            job = scheduler.get_job('bet_monitor')
            if job and job.next_run_time:
                next_check = job.next_run_time.isoformat()
    except Exception as e:
        logger.error(f"Error getting next check time: {e}")
    
    return {
        "enabled": monitoring_enabled,
        "interval": "7-15 minutes (random)",
        "sleep_hours": "10:45 PM - 6:00 AM Arizona",
        "running": scheduler.running,
        "next_check": next_check
    }

@api_router.post("/monitoring/check-now")
async def check_now():
    """Manually trigger a bet check immediately"""
    if not monitoring_enabled:
        raise HTTPException(status_code=400, detail="Monitoring is not enabled. Please start monitoring first.")
    
    # Run the full check cycle (which includes the notification) in background
    asyncio.create_task(monitor_and_reschedule())
    
    return {
        "success": True,
        "message": "Manual bet check triggered. Results will be logged and notifications sent if new bets found."
    }


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    global monitoring_enabled
    monitoring_enabled = False
    if scheduler.running:
        scheduler.shutdown()
    client.close()
    await plays888_service.close()
