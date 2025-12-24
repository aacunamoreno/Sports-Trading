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
    await process_pending_deletions()  # Clean up any scheduled deletions from before restart

async def schedule_message_deletion(chat_id: int, message_id: int, delay_minutes: int = 15):
    """Schedule a message for deletion by storing in database (survives server restarts)"""
    try:
        from zoneinfo import ZoneInfo
        delete_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
        await db.scheduled_deletions.insert_one({
            "chat_id": chat_id,
            "message_id": message_id,
            "delete_at": delete_at,
            "created_at": datetime.now(timezone.utc)
        })
        logger.debug(f"Scheduled message {message_id} for deletion at {delete_at}")
    except Exception as e:
        logger.error(f"Error scheduling message deletion: {e}")

async def process_pending_deletions():
    """Process any messages that are past their deletion time"""
    try:
        now = datetime.now(timezone.utc)
        pending = await db.scheduled_deletions.find({"delete_at": {"$lte": now}}).to_list(100)
        
        if not pending:
            return
        
        logger.info(f"Processing {len(pending)} pending message deletions...")
        
        telegram_config = await db.telegram_config.find_one({}, {"_id": 0})
        if not telegram_config or not telegram_config.get("bot_token"):
            logger.warning("No Telegram config found for deletion processing")
            return
        
        bot = Bot(token=telegram_config["bot_token"])
        
        deleted_count = 0
        for item in pending:
            try:
                await bot.delete_message(chat_id=item["chat_id"], message_id=item["message_id"])
                deleted_count += 1
            except Exception as e:
                # Message may already be deleted or too old
                logger.debug(f"Could not delete message {item['message_id']}: {e}")
            
            # Remove from scheduled deletions regardless of success
            await db.scheduled_deletions.delete_one({"_id": item["_id"]})
        
        if deleted_count > 0:
            logger.info(f"Auto-deleted {deleted_count} status messages")
            
    except Exception as e:
        logger.error(f"Error processing pending deletions: {e}")

async def delete_message_later(bot, chat_id, message_id, delay_minutes=15):
    """Schedule a Telegram message for deletion - now uses database for reliability"""
    # Use database-backed scheduling instead of asyncio task
    await schedule_message_deletion(chat_id, message_id, delay_minutes)

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
        
        # NBA Opportunities refresh at 10:30 PM Arizona (before sleep mode at 10:45 PM)
        scheduler.add_job(
            refresh_nba_opportunities_scheduled,
            trigger=CronTrigger(hour=22, minute=30, timezone='America/Phoenix'),  # 10:30 PM Arizona
            id='nba_opportunities_refresh',
            replace_existing=True
        )
        logger.info("NBA opportunities refresh scheduled for 10:30 PM Arizona time")
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
                                    asyncio.create_task(delete_message_later(bot, telegram_config["chat_id"], sent_msg.message_id, 15))
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
        # Process any pending message deletions first
        await process_pending_deletions()
        
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
        
        # DISABLED: Status notifications to keep chat clean
        # User only wants compilation messages (daily bet summaries)
        # await send_check_notification(check_time, new_bets_found)
        logger.info(f"Check complete - ENANO: {new_bets_found.get('jac075', 0)}, TIPSTER: {new_bets_found.get('jac083', 0)} new bets")
        
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
                    
                    # DISABLED: SYSTEM RESTART notification to keep chat clean
                    # User only wants compilation messages
                    logger.info(f"System restart detected after {hours_since_last:.1f} hours - running catch-up check (no notification sent)")
                    
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


# Team name mapping from plays888 full names to short names for opportunities
PLAYS888_TO_SHORT_TEAM_NAME = {
    # NBA Teams
    'ATLANTA HAWKS': 'Atlanta',
    'BOSTON CELTICS': 'Boston',
    'BROOKLYN NETS': 'Brooklyn',
    'CHARLOTTE HORNETS': 'Charlotte',
    'CHICAGO BULLS': 'Chicago',
    'CLEVELAND CAVALIERS': 'Cleveland',
    'DALLAS MAVERICKS': 'Dallas',
    'DENVER NUGGETS': 'Denver',
    'DETROIT PISTONS': 'Detroit',
    'GOLDEN STATE WARRIORS': 'Golden State',
    'HOUSTON ROCKETS': 'Houston',
    'INDIANA PACERS': 'Indiana',
    'LOS ANGELES CLIPPERS': 'LA Clippers',
    'LOS ANGELES LAKERS': 'LA Lakers',
    'MEMPHIS GRIZZLIES': 'Memphis',
    'MIAMI HEAT': 'Miami',
    'MILWAUKEE BUCKS': 'Milwaukee',
    'MINNESOTA TIMBERWOLVES': 'Minnesota',
    'NEW ORLEANS PELICANS': 'New Orleans',
    'NEW YORK KNICKS': 'New York',
    'OKLAHOMA CITY THUNDER': 'Okla City',
    'ORLANDO MAGIC': 'Orlando',
    'PHILADELPHIA 76ERS': 'Philadelphia',
    'PHOENIX SUNS': 'Phoenix',
    'PORTLAND TRAIL BLAZERS': 'Portland',
    'SACRAMENTO KINGS': 'Sacramento',
    'SAN ANTONIO SPURS': 'San Antonio',
    'TORONTO RAPTORS': 'Toronto',
    'UTAH JAZZ': 'Utah',
    'WASHINGTON WIZARDS': 'Washington',
    # NHL Teams
    'ANAHEIM DUCKS': 'Anaheim',
    'ARIZONA COYOTES': 'Arizona',
    'BOSTON BRUINS': 'Boston',
    'BUFFALO SABRES': 'Buffalo',
    'CALGARY FLAMES': 'Calgary',
    'CAROLINA HURRICANES': 'Carolina',
    'CHICAGO BLACKHAWKS': 'Chicago',
    'COLORADO AVALANCHE': 'Colorado',
    'COLUMBUS BLUE JACKETS': 'Columbus',
    'DALLAS STARS': 'Dallas',
    'DETROIT RED WINGS': 'Detroit',
    'EDMONTON OILERS': 'Edmonton',
    'FLORIDA PANTHERS': 'Florida',
    'LOS ANGELES KINGS': 'Los Angeles',
    'MINNESOTA WILD': 'Minnesota',
    'MONTREAL CANADIENS': 'Montreal',
    'NASHVILLE PREDATORS': 'Nashville',
    'NEW JERSEY DEVILS': 'New Jersey',
    'NEW YORK ISLANDERS': 'NY Islanders',
    'NEW YORK RANGERS': 'NY Rangers',
    'OTTAWA SENATORS': 'Ottawa',
    'PHILADELPHIA FLYERS': 'Philadelphia',
    'PITTSBURGH PENGUINS': 'Pittsburgh',
    'SAN JOSE SHARKS': 'San Jose',
    'SEATTLE KRAKEN': 'Seattle',
    'ST. LOUIS BLUES': 'St. Louis',
    'TAMPA BAY LIGHTNING': 'Tampa Bay',
    'TORONTO MAPLE LEAFS': 'Toronto',
    'UTAH MAMMOTH': 'Utah',  # New team (formerly Arizona Coyotes)
    'VANCOUVER CANUCKS': 'Vancouver',
    'VEGAS GOLDEN KNIGHTS': 'Vegas',
    'WASHINGTON CAPITALS': 'Washington',
    'WINNIPEG JETS': 'Winnipeg',
}

def convert_plays888_team_name(full_name: str) -> str:
    """Convert plays888 full team name to short name for opportunities"""
    return PLAYS888_TO_SHORT_TEAM_NAME.get(full_name.upper(), full_name)


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

async def build_compilation_message(account: str, detailed: bool = False) -> str:
    """Build the compilation message for an account
    
    Args:
        account: The account username
        detailed: If True, use full team names. If False, use short abbreviations.
    """
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
    
    # For ENANO (jac075), get TIPSTER's bets to compare losses
    tipster_bet_keys = set()
    if account == "jac075":
        tipster_compilation = await db.daily_compilations.find_one({
            "account": "jac083",
            "date": today
        })
        if tipster_compilation and tipster_compilation.get('bets'):
            for tb in tipster_compilation['bets']:
                # Create a unique key for each bet (game + bet_type)
                key = f"{tb.get('game_short', '')}-{tb.get('bet_type_short', '')}"
                tipster_bet_keys.add(key)
    
    # Header differs for short vs detailed
    if detailed:
        lines = [f"📋 *{account_label}* (Detail)", ""]
    else:
        lines = [f"👤 *{account_label}*", ""]
    
    for i, bet in enumerate(bets, 1):
        # Use full game name for detailed, short for compact
        if detailed:
            game_name = bet.get('game', bet.get('game_short', 'GAME')).upper()
            # Clean up the game name
            game_name = game_name.replace('REG.TIME', '').strip()
        else:
            game_name = bet.get('game_short', 'GAME')
        
        bet_type_short = bet.get('bet_type_short', '')
        wager_short = bet.get('wager_short', '$0')
        to_win_short = bet.get('to_win_short', '$0')
        result = bet.get('result')
        
        # Build line
        bet_line = f"#{i} {game_name}"
        if bet_type_short:
            bet_line += f" {bet_type_short}"
        bet_line += f" ({wager_short}/{to_win_short})"
        
        # Add result emoji
        if result == 'won':
            bet_line += "🟢"
        elif result == 'lost':
            # For ENANO: check if this loss is also in TIPSTER
            if account == "jac075":
                bet_key = f"{bet.get('game_short', '')}-{bet.get('bet_type_short', '')}"
                if bet_key in tipster_bet_keys:
                    bet_line += "🔴"  # Red: Loss is in both ENANO and TIPSTER
                else:
                    bet_line += "🟠"  # Orange: Loss is only in ENANO
            else:
                bet_line += "🔴"
        elif result == 'push':
            bet_line += "🔵"
        else:
            bet_line += "🟡"
        
        lines.append(bet_line)
    
    # Add result total if any bets are settled
    settled_bets = [b for b in bets if b.get('result') in ['won', 'lost', 'push']]
    if settled_bets:
        lines.append("")
        result_sign = "+" if total_result >= 0 else ""
        lines.append(f"*Result: {result_sign}{format_amount_short(total_result)}*")
        
        # Add records
        if account == "jac075":
            # ENANO: Show 3 records (overall, $2K bets, $1K bets)
            overall_wins = len([b for b in bets if b.get('result') == 'won'])
            overall_losses = len([b for b in bets if b.get('result') == 'lost'])
            
            # $2K bets (includes $2K, $2.2K, etc.)
            bets_2k = [b for b in bets if b.get('wager_short', '').startswith('$2')]
            wins_2k = len([b for b in bets_2k if b.get('result') == 'won'])
            losses_2k = len([b for b in bets_2k if b.get('result') == 'lost'])
            
            # $1K bets (includes $1K, $1.3K, etc.)
            bets_1k = [b for b in bets if b.get('wager_short', '').startswith('$1')]
            wins_1k = len([b for b in bets_1k if b.get('result') == 'won'])
            losses_1k = len([b for b in bets_1k if b.get('result') == 'lost'])
            
            lines.append(f"*Record: {overall_wins}-{overall_losses}*")
            lines.append(f"*$2K: {wins_2k}-{losses_2k}*")
            lines.append(f"*$1K: {wins_1k}-{losses_1k}*")
        else:
            # TIPSTER: Single overall record
            wins = len([b for b in bets if b.get('result') == 'won'])
            losses = len([b for b in bets if b.get('result') == 'lost'])
            lines.append(f"*Record: {wins}-{losses}*")
    
    return "\n".join(lines)

async def update_compilation_message(account: str):
    """Update the Telegram message - ENANO gets short only, TIPSTER gets short + detail"""
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
        
        # Generate short message (for all accounts)
        short_message = await build_compilation_message(account, detailed=False)
        
        # Generate detailed message ONLY for TIPSTER (jac083)
        detailed_message = None
        if account == "jac083":
            detailed_message = await build_compilation_message(account, detailed=True)
        
        if not short_message:
            return
        
        # Delete ALL old messages for this account
        all_compilations = await db.daily_compilations.find({"account": account}).to_list(100)
        for old_comp in all_compilations:
            for field in ['message_id_short', 'message_id_detailed', 'message_id']:
                old_id = old_comp.get(field)
                if old_id:
                    try:
                        await telegram_bot.delete_message(chat_id=telegram_chat_id, message_id=old_id)
                    except Exception:
                        pass
        
        # Send SHORT message
        short_sent = await telegram_bot.send_message(
            chat_id=telegram_chat_id,
            text=short_message,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Send DETAILED message only for TIPSTER
        detailed_sent_id = None
        if detailed_message:
            detailed_sent = await telegram_bot.send_message(
                chat_id=telegram_chat_id,
                text=detailed_message,
                parse_mode=ParseMode.MARKDOWN
            )
            detailed_sent_id = detailed_sent.message_id
        
        # Store message IDs
        await db.daily_compilations.update_one(
            {"account": account, "date": today},
            {"$set": {
                "message_id_short": short_sent.message_id,
                "message_id_detailed": detailed_sent_id,
                "message_id": None
            }}
        )
        logger.info(f"Sent compilation for {account}: short={short_sent.message_id}, detailed={detailed_sent_id}")
        
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

    async def scrape_totals(self, league: str = "NBA") -> List[Dict[str, Any]]:
        """
        Scrape over/under totals from plays888.co for a specific league
        Returns list of games with team names and total lines
        """
        import re
        
        try:
            if not self.page:
                logger.error("Browser not initialized")
                return []
            
            logger.info(f"Scraping {league} totals from plays888.co")
            
            # Navigate directly to the CreateSports page (Straight bets)
            await self.page.goto('https://www.plays888.co/wager/CreateSports.aspx?WT=0', timeout=30000)
            await self.page.wait_for_load_state('networkidle')
            await self.page.wait_for_timeout(2000)
            
            # Determine checkbox ID and continue button based on league
            if league.upper() == "NBA":
                checkbox_id = "lg_3"  # NBA checkbox
                card_heading = "heading4"  # Baloncesto section
            elif league.upper() == "NHL":
                checkbox_id = "lg_1166"  # NHL - OT INCLUDED checkbox
                card_heading = "heading12"  # Hockey section (adjust if needed)
            else:
                logger.error(f"Unsupported league: {league}")
                return []
            
            # Check the league checkbox using JavaScript
            checkbox_result = await self.page.evaluate(f'''
                () => {{
                    const checkbox = document.getElementById("{checkbox_id}");
                    if (checkbox) {{
                        checkbox.checked = true;
                        checkbox.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                    return false;
                }}
            ''')
            
            if not checkbox_result:
                logger.error(f"Could not find checkbox for {league}")
                return []
            
            await self.page.wait_for_timeout(500)
            
            # Click Continue button using JavaScript (ASP.NET postback)
            continue_result = await self.page.evaluate(f'''
                () => {{
                    // Find checkbox and its card
                    const checkbox = document.getElementById("{checkbox_id}");
                    if (!checkbox) return false;
                    
                    const card = checkbox.closest('.card');
                    if (card) {{
                        const continueBtn = card.querySelector('input[value="Continue"]');
                        if (continueBtn) {{
                            continueBtn.click();
                            return true;
                        }}
                    }}
                    
                    // Fallback: trigger ASP.NET postback directly
                    if (typeof __doPostBack !== 'undefined') {{
                        const buttons = document.querySelectorAll('input[value="Continue"]');
                        for (const btn of buttons) {{
                            const rect = btn.getBoundingClientRect();
                            if (rect.top >= 0 && rect.bottom <= window.innerHeight) {{
                                btn.click();
                                return true;
                            }}
                        }}
                    }}
                    return false;
                }}
            ''')
            
            await self.page.wait_for_timeout(5000)
            await self.page.wait_for_load_state('networkidle', timeout=15000)
            
            # Take screenshot for debugging
            await self.page.screenshot(path=f"/tmp/plays888_{league.lower()}_totals.png")
            
            # Get page text for parsing
            page_text = await self.page.inner_text('body')
            
            # Check if error message appeared
            if "select at least one League" in page_text:
                logger.error(f"Failed to select {league} - league selection error")
                return []
            
            # Parse games from the page text
            # NBA format: "541 BROOKLYN NETS" (3 digit game number)
            # NHL format: "53 PITTSBURGH PENGUINS" (2 digit game number)
            games = []
            lines = page_text.split('\n')
            
            i = 0
            current_away_team = None
            current_time = None
            
            while i < len(lines):
                line = lines[i].strip()
                
                # Look for game number + team name pattern (2-3 digit game number)
                team_match = re.match(r'^\d{2,3}\s+(.+)$', line)
                if team_match:
                    team_name = team_match.group(1).strip()
                    
                    # Look ahead for the total line (o/u pattern)
                    # NBA uses format like o219-110 (3 digits), NHL uses o6-120 or o5½-110 (1-2 digits)
                    for j in range(i + 1, min(i + 5, len(lines))):
                        next_line = lines[j].strip()
                        # Updated regex to match 1-3 digit totals
                        total_match = re.match(r'^[ou](\d{1,3}[½]?)[-+]\d+$', next_line, re.IGNORECASE)
                        if total_match:
                            total_str = total_match.group(1).replace('½', '.5')
                            total = float(total_str)
                            
                            if current_away_team:
                                # This is the home team, complete the game
                                games.append({
                                    "away": current_away_team,
                                    "home": team_name,
                                    "total": total,
                                    "time": current_time
                                })
                                current_away_team = None
                                current_time = None
                            else:
                                # This is the away team
                                current_away_team = team_name
                            break
                
                # Look for time pattern (e.g., "4:10 PM")
                time_match = re.match(r'^(\d{1,2}:\d{2}\s*[AP]M)$', line, re.IGNORECASE)
                if time_match and current_away_team:
                    current_time = time_match.group(1)
                
                i += 1
            
            logger.info(f"Found {len(games)} games with totals for {league}")
            return games
            
        except Exception as e:
            logger.error(f"Error scraping totals: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    async def scrape_open_bets(self) -> List[Dict[str, Any]]:
        """
        Scrape open/pending bets from plays888.co
        Returns list of open bets with game info and bet type (over/under)
        """
        import re
        
        # List of official NHL teams to filter out non-NHL hockey leagues
        NHL_TEAMS = [
            'ANAHEIM DUCKS', 'ARIZONA COYOTES', 'BOSTON BRUINS', 'BUFFALO SABRES',
            'CALGARY FLAMES', 'CAROLINA HURRICANES', 'CHICAGO BLACKHAWKS', 'COLORADO AVALANCHE',
            'COLUMBUS BLUE JACKETS', 'DALLAS STARS', 'DETROIT RED WINGS', 'EDMONTON OILERS',
            'FLORIDA PANTHERS', 'LOS ANGELES KINGS', 'MINNESOTA WILD', 'MONTREAL CANADIENS',
            'NASHVILLE PREDATORS', 'NEW JERSEY DEVILS', 'NEW YORK ISLANDERS', 'NEW YORK RANGERS',
            'OTTAWA SENATORS', 'PHILADELPHIA FLYERS', 'PITTSBURGH PENGUINS', 'SAN JOSE SHARKS',
            'SEATTLE KRAKEN', 'ST. LOUIS BLUES', 'TAMPA BAY LIGHTNING', 'TORONTO MAPLE LEAFS',
            'UTAH MAMMOTH', 'VANCOUVER CANUCKS', 'VEGAS GOLDEN KNIGHTS', 'WASHINGTON CAPITALS',
            'WINNIPEG JETS'
        ]
        
        # NBA teams for filtering
        NBA_TEAMS = [
            'ATLANTA HAWKS', 'BOSTON CELTICS', 'BROOKLYN NETS', 'CHARLOTTE HORNETS',
            'CHICAGO BULLS', 'CLEVELAND CAVALIERS', 'DALLAS MAVERICKS', 'DENVER NUGGETS',
            'DETROIT PISTONS', 'GOLDEN STATE WARRIORS', 'HOUSTON ROCKETS', 'INDIANA PACERS',
            'LOS ANGELES CLIPPERS', 'LOS ANGELES LAKERS', 'MEMPHIS GRIZZLIES', 'MIAMI HEAT',
            'MILWAUKEE BUCKS', 'MINNESOTA TIMBERWOLVES', 'NEW ORLEANS PELICANS', 'NEW YORK KNICKS',
            'OKLAHOMA CITY THUNDER', 'ORLANDO MAGIC', 'PHILADELPHIA 76ERS', 'PHOENIX SUNS',
            'PORTLAND TRAIL BLAZERS', 'SACRAMENTO KINGS', 'SAN ANTONIO SPURS', 'TORONTO RAPTORS',
            'UTAH JAZZ', 'WASHINGTON WIZARDS'
        ]
        
        def is_nhl_team(team_name):
            team_upper = team_name.upper()
            return any(nhl_team in team_upper or team_upper in nhl_team for nhl_team in NHL_TEAMS)
        
        def is_nba_team(team_name):
            team_upper = team_name.upper()
            return any(nba_team in team_upper or team_upper in nba_team for nba_team in NBA_TEAMS)
        
        try:
            if not self.page:
                logger.error("Browser not initialized")
                return []
            
            logger.info("Scraping open bets from plays888.co")
            
            # Navigate to Open Bets page
            await self.page.goto('https://www.plays888.co/wager/OpenBets.aspx', timeout=30000)
            await self.page.wait_for_load_state('networkidle')
            await self.page.wait_for_timeout(2000)
            
            # Get page content
            page_text = await self.page.inner_text('body')
            
            # Parse open bets - collect raw bets first
            raw_bets = []
            
            # Pattern to match totals: TOTAL o6-110 or u6-110
            # Format: (TEAM1 vrs TEAM2) or (TEAM1 REG.TIME vrs TEAM2 REG.TIME)
            lines = page_text.split('\n')
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Look for TOTAL lines with o/u
                total_match = re.search(r'TOTAL\s+([ou])(\d+\.?\d*)[½]?[-+]\d+', line, re.IGNORECASE)
                if total_match:
                    bet_type = 'OVER' if total_match.group(1).lower() == 'o' else 'UNDER'
                    total_line = float(total_match.group(2).replace('½', '.5'))
                    
                    # Look for team names in nearby lines
                    teams_text = ""
                    for j in range(max(0, i-2), min(len(lines), i+3)):
                        if 'vrs' in lines[j].lower():
                            teams_text = lines[j]
                            break
                    
                    # Extract team names from "(TEAM1 vrs TEAM2)" or "(TEAM1 REG.TIME vrs TEAM2 REG.TIME)"
                    teams_match = re.search(r'\(([^)]+)\s+(?:REG\.TIME\s+)?vrs\s+([^)]+?)(?:\s+REG\.TIME)?\)', teams_text, re.IGNORECASE)
                    if teams_match:
                        away_team = teams_match.group(1).strip().replace(' REG.TIME', '')
                        home_team = teams_match.group(2).strip().replace(' REG.TIME', '')
                        
                        # Determine sport based on team names (more reliable than context)
                        sport = None
                        if is_nhl_team(away_team) and is_nhl_team(home_team):
                            sport = 'NHL'
                        elif is_nba_team(away_team) and is_nba_team(home_team):
                            sport = 'NBA'
                        
                        # Only add bets for recognized leagues (NHL/NBA)
                        if sport:
                            # Look for risk amount
                            risk_match = re.search(r'(\d{1,},?\d+\.?\d*)\s*/\s*(\d{1,},?\d+\.?\d*)', lines[i+1] if i+1 < len(lines) else '')
                            risk_amount = 0
                            win_amount = 0
                            if risk_match:
                                risk_amount = float(risk_match.group(1).replace(',', ''))
                                win_amount = float(risk_match.group(2).replace(',', ''))
                            
                            raw_bets.append({
                                "sport": sport,
                                "away_team": away_team,
                                "home_team": home_team,
                                "bet_type": bet_type,
                                "total_line": total_line,
                                "risk": risk_amount,
                                "to_win": win_amount
                            })
                
                i += 1
            
            # Consolidate duplicate bets (same game + bet type) and count them
            open_bets = []
            bet_counts = {}
            
            for bet in raw_bets:
                # Create a unique key for each game + bet type combination
                key = f"{bet['sport']}:{bet['away_team']}:{bet['home_team']}:{bet['bet_type']}"
                
                if key in bet_counts:
                    bet_counts[key]['count'] += 1
                    bet_counts[key]['total_risk'] += bet['risk']
                    bet_counts[key]['total_win'] += bet['to_win']
                else:
                    bet_counts[key] = {
                        'bet': bet,
                        'count': 1,
                        'total_risk': bet['risk'],
                        'total_win': bet['to_win']
                    }
            
            # Build final open_bets list with count
            for key, data in bet_counts.items():
                bet = data['bet'].copy()
                bet['bet_count'] = data['count']
                bet['total_risk'] = data['total_risk']
                bet['total_win'] = data['total_win']
                open_bets.append(bet)
            
            logger.info(f"Found {len(open_bets)} unique open bets (from {len(raw_bets)} total)")
            return open_bets
            
        except Exception as e:
            logger.error(f"Error scraping open bets: {str(e)}")
            import traceback
            traceback.print_exc()
            return []


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
        asyncio.create_task(delete_message_later(bot, chat_id, sent_msg.message_id, 15))
        
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


# ============== TELEGRAM CLEANUP ==============

@api_router.post("/telegram/cleanup-now")
async def cleanup_telegram_messages():
    """Manually trigger cleanup of scheduled message deletions"""
    try:
        await process_pending_deletions()
        
        # Count remaining scheduled deletions
        remaining = await db.scheduled_deletions.count_documents({})
        
        return {
            "success": True,
            "message": "Cleanup completed",
            "remaining_scheduled": remaining
        }
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/telegram/scheduled-deletions")
async def get_scheduled_deletions():
    """View all scheduled message deletions"""
    try:
        deletions = await db.scheduled_deletions.find({}, {"_id": 0}).to_list(100)
        now = datetime.now(timezone.utc)
        
        for d in deletions:
            if d.get('delete_at'):
                d['delete_at'] = d['delete_at'].isoformat()
                d['time_remaining'] = str(d.get('delete_at', now) - now) if isinstance(d.get('delete_at'), datetime) else 'N/A'
            if d.get('created_at'):
                d['created_at'] = d['created_at'].isoformat()
        
        return {
            "count": len(deletions),
            "deletions": deletions
        }
    except Exception as e:
        logger.error(f"Get scheduled deletions error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/telegram/bulk-cleanup")
async def bulk_cleanup_telegram(start_msg_id: int, end_msg_id: int):
    """Delete a range of messages from Telegram chat to clean up clutter"""
    try:
        telegram_config = await db.telegram_config.find_one({}, {"_id": 0})
        if not telegram_config or not telegram_config.get("bot_token") or not telegram_config.get("chat_id"):
            raise HTTPException(status_code=400, detail="Telegram not configured")
        
        bot = Bot(token=telegram_config["bot_token"])
        chat_id = telegram_config["chat_id"]
        
        deleted_count = 0
        failed_count = 0
        
        for msg_id in range(start_msg_id, end_msg_id + 1):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                deleted_count += 1
            except Exception as e:
                failed_count += 1
                # Message may already be deleted or doesn't exist
                pass
        
        # Also clear scheduled deletions for these messages
        await db.scheduled_deletions.delete_many({
            "message_id": {"$gte": start_msg_id, "$lte": end_msg_id}
        })
        
        return {
            "success": True,
            "deleted": deleted_count,
            "failed": failed_count,
            "range": f"{start_msg_id} to {end_msg_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk cleanup error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/rules/opportunities")
async def get_rules_opportunities():
    """Get current betting opportunities that match rules (from plays888)"""
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


@api_router.get("/open-bets/{account}")
async def get_open_bets(account: str = "ENANO"):
    """Get open/pending bets from plays888.co for a specific account"""
    scrape_service = Plays888Service()
    
    try:
        # Get connection credentials based on account
        # ENANO = jac075, TIPSTER = jac083
        if account.upper() == "ENANO":
            username = "jac075"
        elif account.upper() == "TIPSTER":
            username = "jac083"
        else:
            raise HTTPException(status_code=400, detail=f"Unknown account: {account}")
        
        # Get password from connections
        conn = await db.connections.find_one({"username": username}, {"_id": 0})
        
        if not conn:
            raise HTTPException(status_code=400, detail=f"No connection found for {account}")
        
        password = decrypt_password(conn["password_encrypted"])
        
        # Login and scrape open bets
        await scrape_service.login(username, password)
        open_bets = await scrape_service.scrape_open_bets()
        
        return {
            "success": True,
            "account": account.upper(),
            "open_bets": open_bets,
            "count": len(open_bets)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get open bets error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await scrape_service.close()


@api_router.post("/scrape/totals/{league}")
async def scrape_plays888_totals(league: str):
    """Scrape over/under totals from plays888.co for NBA or NHL"""
    # Create a new service instance for each request
    scrape_service = Plays888Service()
    
    try:
        # Get connection credentials
        conn = await db.connections.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
        
        if not conn:
            raise HTTPException(status_code=400, detail="No plays888 connection configured")
        
        username = conn["username"]
        password = decrypt_password(conn["password_encrypted"])
        
        # Login and scrape
        await scrape_service.login(username, password)
        games = await scrape_service.scrape_totals(league.upper())
        
        return {
            "success": True,
            "league": league.upper(),
            "games": games,
            "count": len(games),
            "screenshot": f"/tmp/plays888_{league.lower()}_totals.png"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scrape totals error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await scrape_service.close()


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
    """Send compilation messages: ENANO short, TIPSTER short, TIPSTER detail"""
    if not telegram_bot or not telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured")
    
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        today = datetime.now(arizona_tz).strftime('%Y-%m-%d')
        
        # Find all compilations for today
        compilations = await db.daily_compilations.find({"date": today}).to_list(10)
        
        if not compilations:
            return {"success": True, "message": "No compilations to send"}
        
        # Delete ALL old messages first
        for comp in compilations:
            for field in ['message_id_short', 'message_id_detailed', 'message_id']:
                old_id = comp.get(field)
                if old_id:
                    try:
                        await telegram_bot.delete_message(chat_id=telegram_chat_id, message_id=old_id)
                    except Exception:
                        pass
        
        message_ids = {}
        sent_count = 0
        
        # 1. ENANO short (jac075)
        enano_short = await build_compilation_message("jac075", detailed=False)
        if enano_short:
            sent = await telegram_bot.send_message(
                chat_id=telegram_chat_id,
                text=enano_short,
                parse_mode=ParseMode.MARKDOWN
            )
            message_ids["jac075_short"] = sent.message_id
            sent_count += 1
        
        # 2. TIPSTER short (jac083)
        tipster_short = await build_compilation_message("jac083", detailed=False)
        if tipster_short:
            sent = await telegram_bot.send_message(
                chat_id=telegram_chat_id,
                text=tipster_short,
                parse_mode=ParseMode.MARKDOWN
            )
            message_ids["jac083_short"] = sent.message_id
            sent_count += 1
        
        # 3. TIPSTER detail (jac083) - NO detail for ENANO
        tipster_detail = await build_compilation_message("jac083", detailed=True)
        if tipster_detail:
            sent = await telegram_bot.send_message(
                chat_id=telegram_chat_id,
                text=tipster_detail,
                parse_mode=ParseMode.MARKDOWN
            )
            message_ids["jac083_detailed"] = sent.message_id
            sent_count += 1
        
        # Update database with new message IDs
        await db.daily_compilations.update_one(
            {"account": "jac075", "date": today},
            {"$set": {
                "message_id_short": message_ids.get("jac075_short"),
                "message_id_detailed": None,
                "message_id": None
            }}
        )
        await db.daily_compilations.update_one(
            {"account": "jac083", "date": today},
            {"$set": {
                "message_id_short": message_ids.get("jac083_short"),
                "message_id_detailed": message_ids.get("jac083_detailed"),
                "message_id": None
            }}
        )
        
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


# ============== NBA OPPORTUNITIES SCRAPING ==============

async def scrape_nba_odds():
    """Scrape NBA odds from TeamRankings"""
    import re
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get("https://www.teamrankings.com/nba/odds/")
        html = response.text
        
        games = []
        # Parse the HTML to extract game data
        # Looking for tables with game info
        
        # Find today's date section
        today_pattern = r'<h2[^>]*>([^<]*December[^<]*2025[^<]*)</h2>(.*?)(?=<h2|$)'
        today_match = re.search(today_pattern, html, re.DOTALL | re.IGNORECASE)
        
        if not today_match:
            # Try to find any games
            logger.warning("Could not find today's games section")
            return games
        
        games_html = today_match.group(2)
        
        # Parse each game row
        game_pattern = r'(\d{1,2}:\d{2}\s*[AP]M\s*EST).*?<a[^>]*>([^<]+)</a>.*?<a[^>]*>([^<]+)</a>.*?(\d+\.?\d*)\s*\|'
        game_matches = re.findall(game_pattern, games_html, re.DOTALL | re.IGNORECASE)
        
        # Simpler approach - just get the key data
        time_pattern = r'<tr[^>]*>.*?(\d{1,2}:\d{2}\s*[AP]M\s*EST)'
        team_pattern = r'teamrankings\.com/nba/team/([^"]+)"[^>]*>([^<]+)</a>'
        total_pattern = r'>(\d{3}\.?\d?)</td>'
        
        return games

async def scrape_nba_ppg_rankings():
    """Scrape NBA Points Per Game rankings"""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get("https://www.teamrankings.com/nba/stat/points-per-game")
        html = response.text
        
        rankings = {}
        rankings_last3 = {}
        
        # Parse rankings table
        import re
        # Pattern to find team rows with rankings
        row_pattern = r'<tr[^>]*>.*?<td[^>]*>(\d+)</td>.*?team/([^"]+)"[^>]*>([^<]+)</a>.*?<td[^>]*>[\d.]+</td>.*?<td[^>]*>([\d.]+)</td>'
        
        matches = re.findall(row_pattern, html, re.DOTALL)
        
        # Team name mapping
        team_map = {
            'denver-nuggets': 'Denver', 'oklahoma-city-thunder': 'Okla City',
            'houston-rockets': 'Houston', 'new-york-knicks': 'New York',
            'miami-heat': 'Miami', 'utah-jazz': 'Utah', 'san-antonio-spurs': 'San Antonio',
            'chicago-bulls': 'Chicago', 'detroit-pistons': 'Detroit', 'atlanta-hawks': 'Atlanta',
            'cleveland-cavaliers': 'Cleveland', 'minnesota-timberwolves': 'Minnesota',
            'orlando-magic': 'Orlando', 'los-angeles-lakers': 'LA Lakers',
            'portland-trail-blazers': 'Portland', 'philadelphia-76ers': 'Philadelphia',
            'boston-celtics': 'Boston', 'new-orleans-pelicans': 'New Orleans',
            'memphis-grizzlies': 'Memphis', 'charlotte-hornets': 'Charlotte',
            'phoenix-suns': 'Phoenix', 'golden-state-warriors': 'Golden State',
            'toronto-raptors': 'Toronto', 'milwaukee-bucks': 'Milwaukee',
            'dallas-mavericks': 'Dallas', 'washington-wizards': 'Washington',
            'sacramento-kings': 'Sacramento', 'los-angeles-clippers': 'LA Clippers',
            'indiana-pacers': 'Indiana', 'brooklyn-nets': 'Brooklyn'
        }
        
        for rank, slug, name, last3 in matches:
            team_name = team_map.get(slug, name)
            rankings[team_name] = int(rank)
        
        return rankings

async def get_nba_opportunities():
    """Get NBA betting opportunities with PPG analysis"""
    from zoneinfo import ZoneInfo
    arizona_tz = ZoneInfo('America/Phoenix')
    today = datetime.now(arizona_tz).strftime('%Y-%m-%d')
    
    # Check if we have cached data for today
    cached = await db.nba_opportunities.find_one({"date": today})
    if cached:
        return cached.get('games', [])
    
    # If no cache, return empty (data will be refreshed by scheduled job)
    return []

async def refresh_nba_opportunities_scheduled():
    """Scheduled job to refresh NBA opportunities data daily at 10:30 PM Arizona"""
    from zoneinfo import ZoneInfo
    arizona_tz = ZoneInfo('America/Phoenix')
    today = datetime.now(arizona_tz).strftime('%Y-%m-%d')
    
    logger.info(f"[Scheduled] Refreshing NBA opportunities for {today}")
    
    try:
        # PPG Rankings (Season) - would be scraped from teamrankings.com in production
        ppg_season = {
            'Denver': 1, 'Okla City': 2, 'Houston': 3, 'New York': 4, 'Miami': 5,
            'Utah': 6, 'San Antonio': 7, 'Chicago': 8, 'Detroit': 9, 'Atlanta': 10,
            'Cleveland': 11, 'Minnesota': 12, 'Orlando': 13, 'LA Lakers': 14, 'Portland': 15,
            'Philadelphia': 16, 'Boston': 17, 'New Orleans': 18, 'Memphis': 19, 'Charlotte': 20,
            'Phoenix': 21, 'Golden State': 22, 'Toronto': 23, 'Milwaukee': 24, 'Dallas': 25,
            'Washington': 26, 'Sacramento': 27, 'LA Clippers': 28, 'Indiana': 29, 'Brooklyn': 30
        }
        
        # PPG Rankings (Last 3 games)
        ppg_last3 = {
            'Chicago': 1, 'Utah': 2, 'New Orleans': 3, 'Atlanta': 4, 'San Antonio': 5,
            'Portland': 6, 'Houston': 7, 'Orlando': 8, 'Dallas': 9, 'Memphis': 10,
            'Denver': 11, 'Philadelphia': 12, 'New York': 13, 'Sacramento': 14, 'Golden State': 15,
            'LA Lakers': 16, 'Cleveland': 17, 'Miami': 18, 'Boston': 19, 'Okla City': 20,
            'Detroit': 21, 'Charlotte': 22, 'Washington': 23, 'Phoenix': 24, 'Brooklyn': 25,
            'Toronto': 26, 'Indiana': 27, 'Minnesota': 28, 'LA Clippers': 29, 'Milwaukee': 30
        }
        
        # Today's games (would be scraped from teamrankings.com/nba/odds/)
        games_raw = [
            {"time": "7:00 PM", "away": "Charlotte", "home": "Cleveland", "total": 239.5},
            {"time": "7:30 PM", "away": "Indiana", "home": "Boston", "total": 226.5},
            {"time": "8:00 PM", "away": "Dallas", "home": "New Orleans", "total": 240.5},
            {"time": "9:00 PM", "away": "Utah", "home": "Denver", "total": 250.5},
            {"time": "9:30 PM", "away": "Memphis", "home": "Okla City", "total": 232.5},
            {"time": "10:00 PM", "away": "Detroit", "home": "Portland", "total": 234.5},
            {"time": "10:00 PM", "away": "Orlando", "home": "Golden State", "total": 227.5},
        ]
        
        # Calculate averages and recommendations
        games = []
        plays = []
        
        for i, g in enumerate(games_raw, 1):
            away_season = ppg_season.get(g['away'], 15)
            away_last3 = ppg_last3.get(g['away'], 15)
            away_avg = (away_season + away_last3) / 2
            
            home_season = ppg_season.get(g['home'], 15)
            home_last3 = ppg_last3.get(g['home'], 15)
            home_avg = (home_season + home_last3) / 2
            
            game_avg = (away_avg + home_avg) / 2
            
            # Determine recommendation (midpoint is 15, +/- 2.5)
            # OVER: 1-12.5 (2.5 below midpoint)
            # UNDER: 17.5-30 (2.5 above midpoint)
            if game_avg <= 12.5:
                recommendation = "OVER"
                color = "green"
            elif game_avg >= 17.5:
                recommendation = "UNDER"
                color = "red"
            else:
                recommendation = None
                color = "neutral"
            
            game_data = {
                "game_num": i,
                "time": g['time'],
                "away_team": g['away'],
                "away_ppg_rank": away_season,
                "away_last3_rank": away_last3,
                "away_avg": round(away_avg, 1),
                "home_team": g['home'],
                "home_ppg_rank": home_season,
                "home_last3_rank": home_last3,
                "home_avg": round(home_avg, 1),
                "total": g['total'],
                "game_avg": round(game_avg, 1),
                "recommendation": recommendation,
                "color": color
            }
            games.append(game_data)
            
            if recommendation:
                plays.append({
                    "game": f"{g['away']} @ {g['home']}",
                    "total": g['total'],
                    "game_avg": round(game_avg, 1),
                    "recommendation": recommendation,
                    "color": color
                })
        
        # Save to database
        await db.nba_opportunities.update_one(
            {"date": today},
            {"$set": {
                "date": today,
                "last_updated": datetime.now(arizona_tz).strftime('%I:%M %p'),
                "games": games,
                "plays": plays
            }},
            upsert=True
        )
        
        logger.info(f"[Scheduled] NBA opportunities refreshed successfully: {len(games)} games, {len(plays)} plays")
        
    except Exception as e:
        logger.error(f"[Scheduled] Error refreshing NBA opportunities: {e}")

# ============== COMPOUND RECORD TRACKING ==============

@api_router.get("/opportunities/record/{league}")
async def get_compound_record(league: str):
    """Get the compound record for a league (NBA or NHL)"""
    try:
        league = league.upper()
        record = await db.compound_records.find_one({"league": league}, {"_id": 0})
        
        if record:
            return {
                "league": league,
                "hits": record.get('hits', 0),
                "misses": record.get('misses', 0),
                "last_updated": record.get('last_updated')
            }
        
        return {
            "league": league,
            "hits": 0,
            "misses": 0,
            "last_updated": None
        }
    except Exception as e:
        logger.error(f"Error getting compound record: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/opportunities/record/{league}/update")
async def update_compound_record(league: str, hits: int = 0, misses: int = 0, reset: bool = False):
    """Update the compound record for a league. Use reset=True to reset to 0-0"""
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        league = league.upper()
        
        if reset:
            await db.compound_records.update_one(
                {"league": league},
                {"$set": {
                    "league": league,
                    "hits": 0,
                    "misses": 0,
                    "last_updated": datetime.now(arizona_tz).strftime('%Y-%m-%d %I:%M %p')
                }},
                upsert=True
            )
            return {"success": True, "message": f"{league} record reset to 0-0"}
        
        # Add to existing record
        await db.compound_records.update_one(
            {"league": league},
            {
                "$inc": {"hits": hits, "misses": misses},
                "$set": {"last_updated": datetime.now(arizona_tz).strftime('%Y-%m-%d %I:%M %p')}
            },
            upsert=True
        )
        
        # Get updated record
        record = await db.compound_records.find_one({"league": league}, {"_id": 0})
        return {
            "success": True,
            "league": league,
            "hits": record.get('hits', 0),
            "misses": record.get('misses', 0)
        }
    except Exception as e:
        logger.error(f"Error updating compound record: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/opportunities/record/set")
async def set_compound_record(league: str, hits: int = 0, misses: int = 0):
    """Set the compound record for a league to specific values"""
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        league = league.upper()
        
        await db.compound_records.update_one(
            {"league": league},
            {"$set": {
                "league": league,
                "hits": hits,
                "misses": misses,
                "last_updated": datetime.now(arizona_tz).strftime('%Y-%m-%d %I:%M %p')
            }},
            upsert=True
        )
        
        return {
            "success": True,
            "league": league,
            "hits": hits,
            "misses": misses
        }
    except Exception as e:
        logger.error(f"Error setting compound record: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/opportunities")
async def get_opportunities(day: str = "today"):
    """Get NBA betting opportunities. day parameter: 'yesterday', 'today' or 'tomorrow'"""
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        
        if day == "tomorrow":
            target_date = (datetime.now(arizona_tz) + timedelta(days=1)).strftime('%Y-%m-%d')
        elif day == "yesterday":
            target_date = (datetime.now(arizona_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            target_date = datetime.now(arizona_tz).strftime('%Y-%m-%d')
        
        # Get cached NBA opportunities
        cached = await db.nba_opportunities.find_one({"date": target_date}, {"_id": 0})
        
        # Get compound record
        record = await db.compound_records.find_one({"league": "NBA"}, {"_id": 0})
        compound_record = {
            "hits": record.get('hits', 0) if record else 0,
            "misses": record.get('misses', 0) if record else 0
        }
        
        if cached and cached.get('games'):
            return {
                "success": True,
                "date": target_date,
                "last_updated": cached.get('last_updated'),
                "games": cached.get('games', []),
                "plays": cached.get('plays', []),
                "compound_record": compound_record,
                "data_source": cached.get('data_source', 'hardcoded')
            }
        
        return {
            "success": True,
            "date": target_date,
            "message": "No opportunities data yet. Data refreshes daily before 10:45 PM Arizona.",
            "games": [],
            "plays": [],
            "compound_record": compound_record,
            "data_source": None
        }
    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/opportunities/refresh")
async def refresh_opportunities(day: str = "today", use_live_lines: bool = False):
    """Manually refresh NBA opportunities data. 
    day parameter: 'yesterday', 'today' or 'tomorrow'
    use_live_lines: if True, fetch O/U lines from plays888.co instead of hardcoded values
    """
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        
        if day == "tomorrow":
            target_date = (datetime.now(arizona_tz) + timedelta(days=1)).strftime('%Y-%m-%d')
        elif day == "yesterday":
            target_date = (datetime.now(arizona_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            target_date = datetime.now(arizona_tz).strftime('%Y-%m-%d')
        
        # PPG Rankings (Season)
        ppg_season = {
            'Denver': 1, 'Okla City': 2, 'Houston': 3, 'New York': 4, 'Miami': 5,
            'Utah': 6, 'San Antonio': 7, 'Chicago': 8, 'Detroit': 9, 'Atlanta': 10,
            'Cleveland': 11, 'Minnesota': 12, 'Orlando': 13, 'LA Lakers': 14, 'Portland': 15,
            'Philadelphia': 16, 'Boston': 17, 'New Orleans': 18, 'Memphis': 19, 'Charlotte': 20,
            'Phoenix': 21, 'Golden State': 22, 'Toronto': 23, 'Milwaukee': 24, 'Dallas': 25,
            'Washington': 26, 'Sacramento': 27, 'LA Clippers': 28, 'Indiana': 29, 'Brooklyn': 30
        }
        
        # PPG Rankings (Last 3 games)
        ppg_last3 = {
            'Chicago': 1, 'Utah': 2, 'New Orleans': 3, 'Atlanta': 4, 'San Antonio': 5,
            'Portland': 6, 'Houston': 7, 'Orlando': 8, 'Dallas': 9, 'Memphis': 10,
            'Denver': 11, 'Philadelphia': 12, 'New York': 13, 'Sacramento': 14, 'Golden State': 15,
            'LA Lakers': 16, 'Cleveland': 17, 'Miami': 18, 'Boston': 19, 'Okla City': 20,
            'Detroit': 21, 'Charlotte': 22, 'Washington': 23, 'Phoenix': 24, 'Brooklyn': 25,
            'Toronto': 26, 'Indiana': 27, 'Minnesota': 28, 'LA Clippers': 29, 'Milwaukee': 30
        }
        
        # Actual PPG values (Season 2025)
        ppg_season_values = {
            'Denver': 124.7, 'Okla City': 122.5, 'Houston': 121.0, 'New York': 120.8, 'Miami': 120.2,
            'Utah': 119.9, 'San Antonio': 119.8, 'Chicago': 119.5, 'Detroit': 118.9, 'Atlanta': 118.7,
            'Cleveland': 118.7, 'Minnesota': 118.6, 'Orlando': 118.1, 'LA Lakers': 118.0, 'Portland': 118.0,
            'Philadelphia': 117.0, 'Boston': 116.5, 'New Orleans': 115.3, 'Memphis': 114.7, 'Charlotte': 114.5,
            'Phoenix': 114.3, 'Golden State': 114.0, 'Toronto': 113.5, 'Milwaukee': 113.1, 'Dallas': 113.0,
            'Washington': 112.7, 'Sacramento': 111.5, 'LA Clippers': 110.6, 'Indiana': 110.2, 'Brooklyn': 109.1
        }
        
        # Actual PPG values (Last 3 games)
        ppg_last3_values = {
            'Chicago': 138.3, 'Utah': 134.0, 'New Orleans': 125.0, 'Atlanta': 124.7, 'San Antonio': 123.0,
            'Portland': 122.7, 'Houston': 122.3, 'Orlando': 121.0, 'Dallas': 121.0, 'Memphis': 119.7,
            'Denver': 118.3, 'Philadelphia': 118.0, 'New York': 117.7, 'Sacramento': 117.0, 'Golden State': 116.0,
            'LA Lakers': 115.7, 'Cleveland': 115.7, 'Miami': 115.7, 'Boston': 115.3, 'Okla City': 112.7,
            'Detroit': 112.7, 'Charlotte': 112.7, 'Washington': 112.3, 'Phoenix': 109.7, 'Brooklyn': 106.0,
            'Toronto': 96.0, 'Indiana': 103.7, 'Minnesota': 108.3, 'LA Clippers': 102.3, 'Milwaukee': 95.7
        }
        
        games_raw = []
        data_source = "hardcoded"
        open_bets = []
        
        # Try to fetch live lines from plays888.co if requested and for today's games
        if use_live_lines and day == "today":
            try:
                # Get connection credentials
                conn = await db.connections.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
                if conn and conn.get("is_connected"):
                    username = conn["username"]
                    password = decrypt_password(conn["password_encrypted"])
                    
                    # Create new scraper instance
                    scraper = Plays888Service()
                    await scraper.login(username, password)
                    live_games = await scraper.scrape_totals("NBA")
                    
                    # Also fetch open bets for ENANO account
                    # Re-login as ENANO to get open bets
                    await scraper.close()
                    scraper = Plays888Service()
                    await scraper.login("jac075", decrypt_password((await db.connections.find_one({"username": "jac075"}, {"_id": 0}))["password_encrypted"]))
                    open_bets = await scraper.scrape_open_bets()
                    await scraper.close()
                    
                    if live_games:
                        # Convert plays888 data to our format
                        for game in live_games:
                            away_short = convert_plays888_team_name(game.get('away', ''))
                            home_short = convert_plays888_team_name(game.get('home', ''))
                            games_raw.append({
                                "time": game.get('time', ''),
                                "away": away_short,
                                "home": home_short,
                                "total": game.get('total', 220.0)
                            })
                        data_source = "plays888.co"
                        logger.info(f"Fetched {len(games_raw)} NBA games from plays888.co")
            except Exception as e:
                logger.error(f"Error fetching live lines: {e}")
                # Fall back to hardcoded data
        
        # Use hardcoded data if live fetch failed or wasn't requested
        if not games_raw:
            if day == "tomorrow":
                # Christmas Day NBA games (Dec 25)
                games_raw = [
                    {"time": "9:00 AM", "away": "San Antonio", "home": "New York", "total": 222.5},
                    {"time": "11:30 AM", "away": "Minnesota", "home": "Dallas", "total": 226.5},
                    {"time": "2:00 PM", "away": "Philadelphia", "home": "Boston", "total": 215.0},
                    {"time": "5:00 PM", "away": "LA Lakers", "home": "Golden State", "total": 225.5},
                    {"time": "7:30 PM", "away": "Denver", "home": "Phoenix", "total": 230.0},
                ]
            elif day == "yesterday":
                # Yesterday's NBA games with results (Dec 23)
                # Note: Update final scores once available
                games_raw = [
                    {"time": "4:10 PM", "away": "Brooklyn", "home": "Philadelphia", "total": 219.0, "final_score": None},
                    {"time": "4:10 PM", "away": "Washington", "home": "Charlotte", "total": 238.5, "final_score": None},
                    {"time": "4:40 PM", "away": "Milwaukee", "home": "Indiana", "total": 218.5, "final_score": None},
                    {"time": "4:40 PM", "away": "Toronto", "home": "Miami", "total": 217.5, "final_score": None},
                    {"time": "4:40 PM", "away": "New Orleans", "home": "Cleveland", "total": 245.5, "final_score": None},
                    {"time": "4:40 PM", "away": "Chicago", "home": "Atlanta", "total": 236.0, "final_score": None},
                    {"time": "5:10 PM", "away": "Denver", "home": "Dallas", "total": 228.5, "final_score": None},
                    {"time": "5:10 PM", "away": "New York", "home": "Minnesota", "total": 217.0, "final_score": None},
                    {"time": "5:10 PM", "away": "Okla City", "home": "San Antonio", "total": 233.5, "final_score": None},
                    {"time": "6:10 PM", "away": "LA Lakers", "home": "Phoenix", "total": 219.5, "final_score": None},
                    {"time": "6:10 PM", "away": "Orlando", "home": "Portland", "total": 232.0, "final_score": None},
                    {"time": "7:10 PM", "away": "Detroit", "home": "Sacramento", "total": 225.0, "final_score": None},
                    {"time": "7:40 PM", "away": "Houston", "home": "LA Clippers", "total": 219.0, "final_score": None},
                ]
            elif day == "today":
                # Dec 24 (Christmas Eve) - No NBA games
                games_raw = []
            else:
                # Today's games (Arizona time - hardcoded fallback)
                games_raw = [
                    {"time": "5:00 PM", "away": "Charlotte", "home": "Cleveland", "total": 239.5},
                    {"time": "5:30 PM", "away": "Indiana", "home": "Boston", "total": 226.5},
                    {"time": "6:00 PM", "away": "Dallas", "home": "New Orleans", "total": 240.5},
                    {"time": "7:00 PM", "away": "Utah", "home": "Denver", "total": 250.5},
                    {"time": "7:30 PM", "away": "Memphis", "home": "Okla City", "total": 232.5},
                    {"time": "8:00 PM", "away": "Detroit", "home": "Portland", "total": 234.5},
                    {"time": "8:00 PM", "away": "Orlando", "home": "Golden State", "total": 227.5},
                ]
        
        # Calculate averages and recommendations
        games = []
        plays = []
        
        for i, g in enumerate(games_raw, 1):
            away_season = ppg_season.get(g['away'], 15)
            away_last3 = ppg_last3.get(g['away'], 15)
            away_avg = (away_season + away_last3) / 2
            
            home_season = ppg_season.get(g['home'], 15)
            home_last3 = ppg_last3.get(g['home'], 15)
            home_avg = (home_season + home_last3) / 2
            
            game_avg = (away_avg + home_avg) / 2
            
            # Calculate combined PPG (actual points expected in the game)
            away_season_ppg = ppg_season_values.get(g['away'], 115.0)
            away_last3_ppg = ppg_last3_values.get(g['away'], 115.0)
            home_season_ppg = ppg_season_values.get(g['home'], 115.0)
            home_last3_ppg = ppg_last3_values.get(g['home'], 115.0)
            
            # Combined PPG = average of (season totals + last 3 totals)
            season_total = away_season_ppg + home_season_ppg
            last3_total = away_last3_ppg + home_last3_ppg
            combined_ppg = (season_total + last3_total) / 2
            
            # Check if we have a valid line from plays888.co
            # If total is None or 0, it means "NO LINE" - game not active in plays888
            has_line = g.get('total') and g['total'] > 0
            
            # SIMPLIFIED LOGIC: Determine recommendation based on PPG vs Line comparison
            # If PPG average > Line → OVER (we expect more points than the line)
            # If PPG average < Line → UNDER (we expect fewer points than the line)
            recommendation = None
            color = "neutral"
            
            if has_line:
                edge_value = combined_ppg - g['total']  # Positive = OVER, Negative = UNDER
                
                # Recommend based on which side has the edge
                # Edge must be at least 0.5 points to make a recommendation
                if edge_value >= 0.5:  # PPG is significantly higher than line
                    recommendation = "OVER"
                    color = "green"
                elif edge_value <= -0.5:  # PPG is significantly lower than line
                    recommendation = "UNDER"
                    color = "red"
            
            game_data = {
                "game_num": i,
                "time": g['time'],
                "away_team": g['away'],
                "away_ppg_rank": away_season,
                "away_last3_rank": away_last3,
                "away_avg": round(away_avg, 1),
                "home_team": g['home'],
                "home_ppg_rank": home_season,
                "home_last3_rank": home_last3,
                "home_avg": round(home_avg, 1),
                "total": g['total'] if has_line else None,  # Show None if no line
                "has_line": has_line,
                "combined_ppg": round(combined_ppg, 1),
                "game_avg": round(game_avg, 1),
                "recommendation": recommendation,
                "color": color,
                "has_bet": False,
                "bet_type": None,
                "bet_risk": 0,
                "bet_count": 0
            }
            
            # Check if this game has an active bet
            # Also detect "hedged" bets (both OVER and UNDER on same game = cancelled out)
            game_bets = []
            for bet in open_bets:
                if bet.get('sport') == 'NBA':
                    # Match team names (case-insensitive partial match)
                    bet_away = bet.get('away_team', '').upper()
                    bet_home = bet.get('home_team', '').upper()
                    game_away = g['away'].upper()
                    game_home = g['home'].upper()
                    
                    # Check if teams match (partial match for city names)
                    away_match = any(part in bet_away for part in game_away.split()) or any(part in game_away for part in bet_away.split())
                    home_match = any(part in bet_home for part in game_home.split()) or any(part in game_home for part in bet_home.split())
                    
                    if away_match and home_match:
                        game_bets.append(bet)
            
            # Check if game is hedged (has both OVER and UNDER bets)
            bet_types = [b.get('bet_type', '').upper() for b in game_bets]
            is_hedged = 'OVER' in bet_types and 'UNDER' in bet_types
            
            if game_bets and not is_hedged:
                # Game has active bet(s) that are not hedged
                game_data["has_bet"] = True
                game_data["bet_type"] = game_bets[0].get('bet_type')
                game_data["bet_risk"] = sum(b.get('total_risk', b.get('risk', 0)) for b in game_bets)
                game_data["bet_count"] = sum(b.get('bet_count', 1) for b in game_bets)
                # Store the line at which the bet was placed
                game_data["bet_line"] = game_bets[0].get('total_line')
            elif is_hedged:
                # Game is hedged (OVER + UNDER = push/cancelled)
                game_data["has_bet"] = False
                game_data["is_hedged"] = True
                game_data["bet_type"] = "HEDGED"
                game_data["bet_risk"] = 0
                game_data["bet_count"] = 0
                game_data["bet_line"] = None
            
            # Add result data for yesterday
            if day == "yesterday" and 'final_score' in g:
                game_data["final_score"] = g['final_score']
                # Calculate if recommendation hit (only if we have final score)
                if recommendation and g['final_score'] is not None:
                    if recommendation == "OVER":
                        game_data["result_hit"] = g['final_score'] > g['total']
                    else:  # UNDER
                        game_data["result_hit"] = g['final_score'] < g['total']
                else:
                    game_data["result_hit"] = None
            
            # Calculate edge for all games
            edge = abs(combined_ppg - g['total']) if has_line else 0
            game_data["edge"] = round(edge, 1) if has_line else None
            
            games.append(game_data)
            
            # Only add to plays if this game has an active bet
            if game_data.get("has_bet", False):
                # Calculate bet_edge using the line at which the bet was placed
                bet_line = game_data.get("bet_line")
                if bet_line:
                    bet_edge = abs(combined_ppg - bet_line)
                else:
                    bet_edge = edge  # fallback to current edge if no bet_line
                    
                plays.append({
                    "game": f"{g['away']} @ {g['home']}",
                    "total": g['total'],  # Current live line
                    "bet_line": bet_line,  # Line when bet was placed
                    "combined_ppg": round(combined_ppg, 1),
                    "edge": round(bet_edge, 1),  # Edge at bet time
                    "live_edge": round(edge, 1),  # Current live edge
                    "game_avg": round(game_avg, 1),
                    "recommendation": recommendation,
                    "color": color,
                    "has_bet": True,
                    "bet_type": game_data.get("bet_type"),
                    "bet_risk": game_data.get("bet_risk", 0),
                    "bet_count": game_data.get("bet_count", 0)
                })
        
        # Save to database
        await db.nba_opportunities.update_one(
            {"date": target_date},
            {"$set": {
                "date": target_date,
                "last_updated": datetime.now(arizona_tz).strftime('%I:%M %p'),
                "games": games,
                "plays": plays,
                "data_source": data_source
            }},
            upsert=True
        )
        
        return {
            "success": True,
            "message": f"Opportunities refreshed (source: {data_source})",
            "date": target_date,
            "last_updated": datetime.now(arizona_tz).strftime('%I:%M %p'),
            "games": games,
            "plays": plays,
            "data_source": data_source
        }
    except Exception as e:
        logger.error(f"Error refreshing opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============== NHL OPPORTUNITIES ==============

@api_router.get("/opportunities/nhl")
async def get_nhl_opportunities(day: str = "today"):
    """Get NHL betting opportunities. day parameter: 'yesterday', 'today' or 'tomorrow'"""
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        
        if day == "tomorrow":
            target_date = (datetime.now(arizona_tz) + timedelta(days=1)).strftime('%Y-%m-%d')
        elif day == "yesterday":
            target_date = (datetime.now(arizona_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            target_date = datetime.now(arizona_tz).strftime('%Y-%m-%d')
        
        # Get cached NHL opportunities
        cached = await db.nhl_opportunities.find_one({"date": target_date}, {"_id": 0})
        
        # Get compound record
        record = await db.compound_records.find_one({"league": "NHL"}, {"_id": 0})
        compound_record = {
            "hits": record.get('hits', 0) if record else 0,
            "misses": record.get('misses', 0) if record else 0
        }
        
        if cached and cached.get('games'):
            return {
                "success": True,
                "date": target_date,
                "last_updated": cached.get('last_updated'),
                "games": cached.get('games', []),
                "plays": cached.get('plays', []),
                "compound_record": compound_record,
                "data_source": cached.get('data_source', 'hardcoded')
            }
        
        return {
            "success": True,
            "date": target_date,
            "message": "No NHL opportunities data yet. Click refresh to load games.",
            "games": [],
            "plays": [],
            "compound_record": compound_record,
            "data_source": None
        }
    except Exception as e:
        logger.error(f"Error getting NHL opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/opportunities/nhl/refresh")
async def refresh_nhl_opportunities(day: str = "today", use_live_lines: bool = False):
    """Manually refresh NHL opportunities data. 
    day parameter: 'yesterday', 'today' or 'tomorrow'
    use_live_lines: if True, fetch O/U lines from plays888.co instead of hardcoded values
    """
    try:
        from zoneinfo import ZoneInfo
        arizona_tz = ZoneInfo('America/Phoenix')
        
        if day == "tomorrow":
            target_date = (datetime.now(arizona_tz) + timedelta(days=1)).strftime('%Y-%m-%d')
        elif day == "yesterday":
            target_date = (datetime.now(arizona_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            target_date = datetime.now(arizona_tz).strftime('%Y-%m-%d')
        
        # NHL GPG Rankings (Season) - from ESPN data
        gpg_season = {
            'Colorado': 1, 'Dallas': 2, 'Anaheim': 3, 'Edmonton': 4, 'Carolina': 5,
            'Ottawa': 6, 'Tampa Bay': 7, 'Montreal': 8, 'Boston': 9, 'Washington': 10,
            'Florida': 11, 'Toronto': 12, 'Detroit': 13, 'Utah': 14, 'Pittsburgh': 15,
            'Buffalo': 16, 'Minnesota': 17, 'San Jose': 18, 'Winnipeg': 19, 'Columbus': 20,
            'Philadelphia': 21, 'NY Islanders': 22, 'Chicago': 23, 'Vancouver': 24, 'Nashville': 25,
            'Vegas': 26, 'New Jersey': 27, 'Calgary': 28, 'Los Angeles': 29, 'St. Louis': 30,
            'Seattle': 31, 'NY Rangers': 32
        }
        
        # NHL Goals Last 3 Games Rankings - from StatMuse data
        gpg_last3 = {
            'Dallas': 1, 'Ottawa': 2, 'Calgary': 3, 'Colorado': 4, 'Montreal': 5,
            'Minnesota': 6, 'Carolina': 7, 'Philadelphia': 8, 'Vancouver': 9, 'San Jose': 10,
            'Buffalo': 11, 'Anaheim': 12, 'Edmonton': 13, 'Detroit': 14, 'Utah': 15,
            'Columbus': 16, 'Seattle': 17, 'Tampa Bay': 18, 'Washington': 19, 'St. Louis': 20,
            'Florida': 21, 'Nashville': 22, 'Boston': 23, 'NY Rangers': 24, 'Vegas': 25,
            'Toronto': 26, 'Pittsburgh': 27, 'NY Islanders': 28, 'New Jersey': 29, 'Chicago': 30,
            'Winnipeg': 31, 'Los Angeles': 32
        }
        
        # Actual GPG values (Season) - for combined calculation
        gpg_season_values = {
            'Colorado': 4.03, 'Dallas': 3.51, 'Anaheim': 3.44, 'Edmonton': 3.38, 'Carolina': 3.29,
            'Ottawa': 3.26, 'Tampa Bay': 3.23, 'Montreal': 3.19, 'Boston': 3.19, 'Washington': 3.17,
            'Florida': 3.14, 'Toronto': 3.11, 'Detroit': 3.08, 'Utah': 3.05, 'Pittsburgh': 3.03,
            'Buffalo': 3.03, 'Minnesota': 3.03, 'San Jose': 2.94, 'Winnipeg': 2.91, 'Columbus': 2.89,
            'Philadelphia': 2.88, 'NY Islanders': 2.83, 'Chicago': 2.80, 'Vancouver': 2.80, 'Nashville': 2.80,
            'Vegas': 2.76, 'New Jersey': 2.66, 'Calgary': 2.64, 'Los Angeles': 2.56, 'St. Louis': 2.54,
            'Seattle': 2.52, 'NY Rangers': 2.50
        }
        
        # GPG Last 3 Games values - for combined calculation
        gpg_last3_values = {
            'Dallas': 6.00, 'Ottawa': 5.33, 'Calgary': 4.33, 'Colorado': 4.33, 'Montreal': 3.67,
            'Minnesota': 3.67, 'Carolina': 3.67, 'Philadelphia': 3.67, 'Vancouver': 3.67, 'San Jose': 3.67,
            'Buffalo': 3.33, 'Anaheim': 3.33, 'Edmonton': 3.00, 'Detroit': 3.00, 'Utah': 3.00,
            'Columbus': 3.00, 'Seattle': 3.00, 'Tampa Bay': 3.00, 'Washington': 2.67, 'St. Louis': 2.67,
            'Florida': 2.67, 'Nashville': 2.67, 'Boston': 2.33, 'NY Rangers': 2.33, 'Vegas': 2.33,
            'Toronto': 2.33, 'Pittsburgh': 2.33, 'NY Islanders': 2.33, 'New Jersey': 2.33, 'Chicago': 2.00,
            'Winnipeg': 2.00, 'Los Angeles': 2.00
        }
        
        games_raw = []
        data_source = "hardcoded"
        open_bets = []
        
        # Try to fetch live lines from plays888.co if requested and for today's games
        if use_live_lines and day == "today":
            try:
                # Get connection credentials
                conn = await db.connections.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
                if conn and conn.get("is_connected"):
                    username = conn["username"]
                    password = decrypt_password(conn["password_encrypted"])
                    
                    # Create new scraper instance
                    scraper = Plays888Service()
                    await scraper.login(username, password)
                    live_games = await scraper.scrape_totals("NHL")
                    
                    # Also fetch open bets for ENANO account
                    await scraper.close()
                    scraper = Plays888Service()
                    enano_conn = await db.connections.find_one({"username": "jac075"}, {"_id": 0})
                    if enano_conn:
                        await scraper.login("jac075", decrypt_password(enano_conn["password_encrypted"]))
                        open_bets = await scraper.scrape_open_bets()
                        await scraper.close()
                    
                    if live_games:
                        # Convert plays888 data to our format
                        for game in live_games:
                            away_short = convert_plays888_team_name(game.get('away', ''))
                            home_short = convert_plays888_team_name(game.get('home', ''))
                            games_raw.append({
                                "time": game.get('time', ''),
                                "away": away_short,
                                "home": home_short,
                                "total": game.get('total', 6.0)
                            })
                        data_source = "plays888.co"
                        logger.info(f"Fetched {len(games_raw)} NHL games from plays888.co")
            except Exception as e:
                logger.error(f"Error fetching live NHL lines: {e}")
        
        # Use hardcoded data if live fetch failed or wasn't requested
        if not games_raw:
            if day == "tomorrow":
                # Dec 25 (Christmas Day) - No NHL games
                games_raw = []
            elif day == "yesterday":
                # Yesterday's NHL games with results (Dec 23)
                # Note: Update final scores once available
                games_raw = [
                    {"time": "12:00 PM", "away": "Pittsburgh", "home": "Toronto", "total": 6.0, "final_score": None},
                    {"time": "3:30 PM", "away": "Dallas", "home": "Detroit", "total": 6.0, "final_score": None},
                    {"time": "4:00 PM", "away": "NY Rangers", "home": "Washington", "total": 5.5, "final_score": None},
                    {"time": "4:00 PM", "away": "Florida", "home": "Carolina", "total": 6.0, "final_score": None},
                    {"time": "4:00 PM", "away": "New Jersey", "home": "NY Islanders", "total": 6.0, "final_score": None},
                    {"time": "4:00 PM", "away": "Buffalo", "home": "Ottawa", "total": 6.5, "final_score": None},
                    {"time": "4:00 PM", "away": "Montreal", "home": "Boston", "total": 5.5, "final_score": None},
                    {"time": "5:00 PM", "away": "Nashville", "home": "Minnesota", "total": 5.5, "final_score": None},
                    {"time": "6:00 PM", "away": "Calgary", "home": "Edmonton", "total": 6.5, "final_score": None},
                    {"time": "6:00 PM", "away": "Philadelphia", "home": "Chicago", "total": 6.0, "final_score": None},
                    {"time": "7:00 PM", "away": "Utah", "home": "Colorado", "total": 6.0, "final_score": None},
                    {"time": "7:00 PM", "away": "San Jose", "home": "Vegas", "total": 6.0, "final_score": None},
                    {"time": "7:30 PM", "away": "Seattle", "home": "Los Angeles", "total": 6.0, "final_score": None},
                ]
            elif day == "today":
                # Dec 24 (Christmas Eve) - No NHL games
                games_raw = []
            else:
                # Default fallback - empty
                games_raw = []
        
        # Add games from open bets that might have started but aren't in the schedule
        # This ensures we show all games with active bets
        if day == "today":
            existing_matchups = set()
            for g in games_raw:
                # Create a normalized matchup key
                away_norm = g['away'].upper().split()[-1]  # Last word of team name
                home_norm = g['home'].upper().split()[-1]
                existing_matchups.add(f"{away_norm}:{home_norm}")
            
            added_from_bets = set()  # Track what we've added from bets to avoid duplicates
            for bet in open_bets:
                if bet.get('sport') == 'NHL':
                    bet_away = bet.get('away_team', '').upper()
                    bet_home = bet.get('home_team', '').upper()
                    # Extract last word (team name) for matching
                    bet_away_norm = bet_away.split()[-1] if bet_away else ''
                    bet_home_norm = bet_home.split()[-1] if bet_home else ''
                    matchup_key = f"{bet_away_norm}:{bet_home_norm}"
                    
                    if matchup_key not in existing_matchups and matchup_key not in added_from_bets:
                        # This bet's game isn't in the schedule - add it
                        # Map team names back to short form
                        team_map = {
                            'PENGUINS': 'Pittsburgh', 'MAPLE LEAFS': 'Toronto', 'LEAFS': 'Toronto',
                            'STARS': 'Dallas', 'RED WINGS': 'Detroit', 'WINGS': 'Detroit',
                            'RANGERS': 'NY Rangers', 'CAPITALS': 'Washington',
                            'PANTHERS': 'Florida', 'HURRICANES': 'Carolina',
                            'DEVILS': 'New Jersey', 'ISLANDERS': 'NY Islanders',
                            'SABRES': 'Buffalo', 'SENATORS': 'Ottawa',
                            'CANADIENS': 'Montreal', 'BRUINS': 'Boston',
                            'PREDATORS': 'Nashville', 'WILD': 'Minnesota',
                            'FLYERS': 'Philadelphia', 'BLACKHAWKS': 'Chicago',
                            'MAMMOTH': 'Utah', 'AVALANCHE': 'Colorado',
                            'FLAMES': 'Calgary', 'OILERS': 'Edmonton',
                            'SHARKS': 'San Jose', 'KNIGHTS': 'Vegas',
                            'KRAKEN': 'Seattle', 'KINGS': 'Los Angeles', 'DUCKS': 'Anaheim'
                        }
                        away_short = team_map.get(bet_away_norm, bet_away_norm.title())
                        home_short = team_map.get(bet_home_norm, bet_home_norm.title())
                        
                        # Use bet line if available
                        bet_line = bet.get('total_line', 6.0)
                        
                        games_raw.append({
                            "time": "In Progress",
                            "away": away_short,
                            "home": home_short,
                            "total": bet_line
                        })
                        added_from_bets.add(matchup_key)
                        logger.info(f"Added missing bet game: {away_short} @ {home_short} (line: {bet_line})")
        
        # Calculate averages and recommendations
        games = []
        plays = []
        
        for i, g in enumerate(games_raw, 1):
            away_season = gpg_season.get(g['away'], 16)
            away_last3 = gpg_last3.get(g['away'], 16)
            away_avg = (away_season + away_last3) / 2
            
            home_season = gpg_season.get(g['home'], 16)
            home_last3 = gpg_last3.get(g['home'], 16)
            home_avg = (home_season + home_last3) / 2
            
            game_avg = (away_avg + home_avg) / 2
            
            # Calculate combined GPG (actual goals expected in the game)
            away_season_gpg = gpg_season_values.get(g['away'], 3.0)
            away_last3_gpg = gpg_last3_values.get(g['away'], 3.0)
            home_season_gpg = gpg_season_values.get(g['home'], 3.0)
            home_last3_gpg = gpg_last3_values.get(g['home'], 3.0)
            
            # Combined GPG = average of (season totals + last 3 totals)
            season_total = away_season_gpg + home_season_gpg
            last3_total = away_last3_gpg + home_last3_gpg
            combined_gpg = (season_total + last3_total) / 2
            
            # Check if we have a valid line from plays888.co
            has_line = g.get('total') and g['total'] > 0
            
            # SIMPLIFIED LOGIC: Determine recommendation based on GPG vs Line comparison
            # If GPG average > Line → OVER (we expect more goals than the line)
            # If GPG average < Line → UNDER (we expect fewer goals than the line)
            recommendation = None
            color = "neutral"
            
            if has_line:
                edge_value = combined_gpg - g['total']  # Positive = OVER, Negative = UNDER
                # Round to 1 decimal place to avoid floating point precision issues
                edge_value = round(edge_value, 1)
                
                # Recommend based on which side has the edge
                # Edge must be at least 0.6 goals to make a recommendation (NHL)
                if edge_value >= 0.6:  # GPG is significantly higher than line
                    recommendation = "OVER"
                    color = "green"
                elif edge_value <= -0.6:  # GPG is significantly lower than line
                    recommendation = "UNDER"
                    color = "red"
            
            game_data = {
                "game_num": i,
                "time": g['time'],
                "away_team": g['away'],
                "away_gpg_rank": away_season,
                "away_last3_rank": away_last3,
                "away_avg": round(away_avg, 1),
                "home_team": g['home'],
                "home_gpg_rank": home_season,
                "home_last3_rank": home_last3,
                "home_avg": round(home_avg, 1),
                "total": g['total'] if has_line else None,
                "has_line": has_line,
                "combined_gpg": round(combined_gpg, 1),
                "game_avg": round(game_avg, 1),
                "recommendation": recommendation,
                "color": color,
                "has_bet": False,
                "bet_type": None,
                "bet_risk": 0,
                "bet_count": 0
            }
            
            # Check if this game has an active bet
            # Also detect "hedged" bets (both OVER and UNDER on same game = cancelled out)
            game_bets = []
            for bet in open_bets:
                if bet.get('sport') == 'NHL':
                    # Match team names (case-insensitive partial match)
                    bet_away = bet.get('away_team', '').upper()
                    bet_home = bet.get('home_team', '').upper()
                    game_away = g['away'].upper()
                    game_home = g['home'].upper()
                    
                    # Check if teams match (partial match for city names)
                    away_match = any(part in bet_away for part in game_away.split()) or any(part in game_away for part in bet_away.split())
                    home_match = any(part in bet_home for part in game_home.split()) or any(part in game_home for part in bet_home.split())
                    
                    if away_match and home_match:
                        game_bets.append(bet)
            
            # Check if game is hedged (has both OVER and UNDER bets)
            bet_types = [b.get('bet_type', '').upper() for b in game_bets]
            is_hedged = 'OVER' in bet_types and 'UNDER' in bet_types
            
            if game_bets and not is_hedged:
                # Game has active bet(s) that are not hedged
                game_data["has_bet"] = True
                game_data["bet_type"] = game_bets[0].get('bet_type')
                game_data["bet_risk"] = sum(b.get('total_risk', b.get('risk', 0)) for b in game_bets)
                game_data["bet_count"] = sum(b.get('bet_count', 1) for b in game_bets)
                # Store the line at which the bet was placed
                game_data["bet_line"] = game_bets[0].get('total_line')
            elif is_hedged:
                # Game is hedged (OVER + UNDER = push/cancelled)
                game_data["has_bet"] = False
                game_data["is_hedged"] = True
                game_data["bet_type"] = "HEDGED"
                game_data["bet_risk"] = 0
                game_data["bet_count"] = 0
                game_data["bet_line"] = None
            
            # Add result data for yesterday
            if day == "yesterday" and 'final_score' in g:
                game_data["final_score"] = g['final_score']
                # Calculate if recommendation hit (only if we have final score)
                if recommendation and g['final_score'] is not None:
                    if recommendation == "OVER":
                        game_data["result_hit"] = g['final_score'] > g['total']
                    else:  # UNDER
                        game_data["result_hit"] = g['final_score'] < g['total']
                else:
                    game_data["result_hit"] = None
            
            games.append(game_data)
            
            # Calculate edge for ALL games (for the table)
            edge = abs(combined_gpg - g['total']) if has_line else 0
            game_data["edge"] = round(edge, 1) if has_line else None
            
            # Only add to plays if this game has an active bet (and not already in plays)
            if game_data.get("has_bet", False) and has_line:
                game_key = f"{g['away']} @ {g['home']}"
                # Check if this game is already in plays to avoid duplicates
                if not any(p.get('game') == game_key for p in plays):
                    # Calculate bet_edge using the line at which the bet was placed
                    bet_line = game_data.get("bet_line")
                    if bet_line:
                        bet_edge = abs(combined_gpg - bet_line)
                    else:
                        bet_edge = edge  # fallback to current edge if no bet_line
                        
                    plays.append({
                        "game": game_key,
                        "total": g['total'],  # Current live line
                        "bet_line": bet_line,  # Line when bet was placed
                        "combined_gpg": round(combined_gpg, 1),
                        "edge": round(bet_edge, 1),  # Edge at bet time
                        "live_edge": round(edge, 1),  # Current live edge
                        "game_avg": round(game_avg, 1),
                        "recommendation": recommendation,
                        "color": color,
                        "has_bet": True,
                        "bet_type": game_data.get("bet_type"),
                        "bet_risk": game_data.get("bet_risk", 0),
                        "bet_count": game_data.get("bet_count", 0)
                    })
        
        # Save to database
        await db.nhl_opportunities.update_one(
            {"date": target_date},
            {"$set": {
                "date": target_date,
                "last_updated": datetime.now(arizona_tz).strftime('%I:%M %p'),
                "games": games,
                "plays": plays,
                "data_source": data_source
            }},
            upsert=True
        )
        
        return {
            "success": True,
            "message": f"NHL opportunities refreshed (source: {data_source})",
            "date": target_date,
            "last_updated": datetime.now(arizona_tz).strftime('%I:%M %p'),
            "games": games,
            "plays": plays,
            "data_source": data_source
        }
    except Exception as e:
        logger.error(f"Error refreshing NHL opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
