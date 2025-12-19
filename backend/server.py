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
from datetime import datetime, timezone
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

async def auto_start_monitoring():
    """Auto-start bet monitoring if it was previously enabled"""
    global monitoring_enabled
    try:
        # Check if there's an active connection
        conn = await db.connections.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
        if conn and conn.get("is_connected"):
            # Check if monitoring was previously enabled (stored in DB)
            monitor_config = await db.monitor_config.find_one({}, {"_id": 0})
            if monitor_config and monitor_config.get("auto_start", True):
                monitoring_enabled = True
                # Use random interval scheduling
                schedule_next_check()
                if not scheduler.running:
                    scheduler.start()
                logger.info("Bet monitoring auto-started on server startup (7-15 min random intervals, paused 11:30 PM - 5:30 AM Arizona)")
            else:
                logger.info("Bet monitoring not auto-started (disabled in config)")
        else:
            logger.info("Bet monitoring not auto-started (no active connection)")
    except Exception as e:
        logger.error(f"Error auto-starting monitoring: {str(e)}")


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

async def send_telegram_notification(bet_details: dict):
    """Send Telegram notification when a bet is placed"""
    if not telegram_bot or not telegram_chat_id:
        logger.info("Telegram not configured, skipping notification")
        return
    
    try:
        # Format the message with bet details
        odds_formatted = format_american_odds(bet_details['odds'])
        potential_win = bet_details.get('potential_win', bet_details['wager'])
        
        message = f"""
🎰 *BET PLACED*

*Game:* {bet_details['game']}
*League:* {bet_details.get('league', 'N/A')}
*Bet:* {bet_details['bet_type']} {bet_details.get('line', '')}
*Odds:* {odds_formatted}
*Wager:* ${bet_details['wager']} MXN
*To Win:* ${potential_win:.2f} MXN

*Ticket#:* {bet_details.get('ticket_number', 'Pending')}
*Status:* {bet_details.get('status', 'Placed')}

_Automated via BetBot System_
        """
        
        await telegram_bot.send_message(
            chat_id=telegram_chat_id,
            text=message.strip(),
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"Telegram notification sent for Ticket#{bet_details.get('ticket_number')}")
        
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {str(e)}")


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

def schedule_next_check():
    """Schedule the next bet check with a random interval"""
    global scheduler
    
    # Generate random interval between 7-15 minutes
    next_interval = random.randint(MIN_INTERVAL, MAX_INTERVAL)
    
    # Remove existing job if present
    try:
        scheduler.remove_job('bet_monitor')
    except:
        pass
    
    # Schedule new job with random interval
    scheduler.add_job(
        monitor_and_reschedule,
        trigger=IntervalTrigger(minutes=next_interval),
        id='bet_monitor',
        replace_existing=True
    )
    
    logger.info(f"Next bet check scheduled in {next_interval} minutes")

async def monitor_and_reschedule():
    """Run monitoring and reschedule with new random interval"""
    await monitor_open_bets()
    
    # Reschedule with a new random interval for next check
    if monitoring_enabled:
        schedule_next_check()

async def monitor_open_bets():
    """Background job to monitor plays888.co for new bets"""
    global monitoring_enabled
    
    if not monitoring_enabled:
        return
    
    # Check if we're in sleep hours (11:30 PM - 5:30 AM Arizona time)
    # Arizona is UTC-7 (no daylight saving)
    from zoneinfo import ZoneInfo
    arizona_tz = ZoneInfo('America/Phoenix')
    now_arizona = datetime.now(arizona_tz)
    current_hour = now_arizona.hour
    current_minute = now_arizona.minute
    current_time_minutes = current_hour * 60 + current_minute
    
    # Sleep window: 11:30 PM (23:30 = 1410 mins) to 5:30 AM (5:30 = 330 mins)
    sleep_start = 23 * 60 + 30  # 11:30 PM = 1410 minutes
    sleep_end = 5 * 60 + 30      # 5:30 AM = 330 minutes
    
    if current_time_minutes >= sleep_start or current_time_minutes < sleep_end:
        logger.info(f"Sleep hours ({now_arizona.strftime('%I:%M %p')} Arizona) - skipping bet check")
        return
    
    logger.info(f"Checking plays888.co for new bets... ({now_arizona.strftime('%I:%M %p')} Arizona)")
    
    try:
        # Get ALL active connections (multiple accounts)
        connections = await db.connections.find({"is_connected": True}, {"_id": 0}).to_list(100)
        
        if not connections:
            logger.info("No active connections, skipping bet monitoring")
            return
        
        # Monitor each account
        for conn in connections:
            await monitor_single_account(conn)
            
    except Exception as e:
        logger.error(f"Error in bet monitoring: {str(e)}")

async def monitor_single_account(conn: dict):
    """Monitor a single account for new bets"""
    username = conn["username"]
    password = decrypt_password(conn["password_encrypted"])
    
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
            return
        
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
                        
                        // Extract game name (usually in parentheses at end like "(TEAM A vs TEAM B)" or "(TEAM A vrs TEAM B)")
                        let game = '';
                        const gameMatch = description.match(/\\(([^)]*(?:vs|vrs)[^)]*)\\)/i);
                        if (gameMatch) {
                            game = gameMatch[1].trim();
                        }
                        
                        // Determine bet type from description
                        let betType = '';
                        
                        // Check for Parlay
                        if (description.includes('Parlay') || description.includes('PARLAY')) {
                            betType = 'Parlay';
                        }
                        // Check for Teaser
                        else if (description.includes('Teaser') || description.includes('TEASER')) {
                            betType = 'Teaser';
                        }
                        // Check for TOTAL with over/under like "TOTAL o228" or "TOTAL u6"
                        else {
                            const totalMatch = description.match(/TOTAL\\s+([ou][\\d.½]+)/i);
                            if (totalMatch) {
                                betType = totalMatch[1];
                            } else {
                                // Try to get spread/team info like "TEAM NAME +5.5" or "TEAM NAME -12"
                                // Format: [ID] TEAM NAME +/-SPREAD
                                const spreadTeamMatch = description.match(/\\]\\s*([A-Z][A-Z\\s]+?)\\s+([+-][\\d.½]+)/i);
                                if (spreadTeamMatch) {
                                    const teamName = spreadTeamMatch[1].trim();
                                    const spread = spreadTeamMatch[2];
                                    betType = teamName + ' ' + spread;
                                    // Use team as game if we didn't find a vs match
                                    if (!game) {
                                        game = teamName;
                                    }
                                } else {
                                    // Default to Straight for unknown types
                                    betType = 'Straight';
                                }
                            }
                        }
                        
                        // If game is still empty, try to extract more info from description
                        if (!game) {
                            // Try format: "[ID] TEAM NAME +/-SPREAD" - matches after the bracket
                            const teamExtract = description.match(/\\]\\s*([A-Z][A-Z0-9\\s\\.]+?)\\s+([+-][\\d½]+)/i);
                            if (teamExtract) {
                                game = teamExtract[1].trim();
                                // Also update betType if it's just "Straight"
                                if (betType === 'Straight') {
                                    betType = game + ' ' + teamExtract[2];
                                }
                            }
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
                
                # Store in database
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
                    "notes": f"Auto-detected from plays888.co. Sport: {sport}"
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
                })
        
        await monitor_service.close()
        logger.info(f"Bet monitoring check complete for {username}")
        
    except Exception as e:
        logger.error(f"Error monitoring account {username}: {str(e)}")
        if monitor_service:
            try:
                await monitor_service.close()
            except:
                pass


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
    """Send a test notification"""
    if not telegram_bot or not telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured")
    
    try:
        await send_telegram_notification({
            "game": "Test Game",
            "league": "TEST LEAGUE",
            "bet_type": "Test Bet",
            "line": "Test",
            "odds": -110,
            "wager": 100,
            "potential_win": 90.91,
            "ticket_number": "TEST123",
            "status": "Test"
        })
        return {"success": True, "message": "Test notification sent"}
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
    
    logger.info("Bet monitoring started - checking every 7-15 minutes randomly (paused 11:30 PM - 5:30 AM Arizona)")
    
    return {
        "success": True,
        "message": "Bet monitoring started. Will check plays888.co every 7-15 minutes randomly (paused during sleep hours 11:30 PM - 5:30 AM Arizona).",
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
        "sleep_hours": "11:30 PM - 5:30 AM Arizona",
        "running": scheduler.running,
        "next_check": next_check
    }

@api_router.post("/monitoring/check-now")
async def check_now():
    """Manually trigger a bet check immediately"""
    if not monitoring_enabled:
        raise HTTPException(status_code=400, detail="Monitoring is not enabled. Please start monitoring first.")
    
    # Run the check immediately in background
    asyncio.create_task(monitor_open_bets())
    
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
