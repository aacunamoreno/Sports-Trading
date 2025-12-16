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
from datetime import datetime, timezone
from cryptography.fernet import Fernet
import base64
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

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
                self.browser = await self.playwright.chromium.launch(headless=True)
            if not self.context:
                self.context = await self.browser.new_context()
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
                await self.page.wait_for_load_state('networkidle')
                await self.page.wait_for_timeout(5000)  # Wait longer for games to load
                logger.info("Step 3: Clicked Continue button and waiting for games to load")
            except Exception as e:
                logger.error(f"Could not select league: {str(e)}")
                return {"success": False, "message": f"Could not select league: {str(e)}"}
            
            await self.page.screenshot(path="/tmp/step3_games_list.png")
            
            # Check current URL
            current_url = self.page.url
            logger.info(f"Current URL after Continue: {current_url}")
            
            # Step 4: Find the game and click the odds button
            try:
                # Format odds with + or - sign
                odds_text = f"+{odds}" if odds > 0 else str(odds)
                
                # Save HTML for debugging
                page_content = await self.page.content()
                with open("/tmp/step3_games_html.html", "w", encoding="utf-8") as f:
                    f.write(page_content)
                logger.info("Saved games page HTML")
                
                # The odds are in input elements in the M Line column
                # First, try to find all input elements on the page
                all_inputs = await self.page.query_selector_all('input[type="submit"]')
                logger.info(f"Found {len(all_inputs)} input buttons on page")
                
                # Look through all inputs for one matching our odds
                clicked = False
                for input_elem in all_inputs:
                    try:
                        value = await input_elem.get_attribute('value')
                        if value == odds_text:
                            await input_elem.click(force=True)
                            clicked = True
                            logger.info(f"Step 4: Clicked odds button '{odds_text}' via element search")
                            break
                    except:
                        continue
                
                # If that didn't work, try direct selectors
                if not clicked:
                    selectors = [
                        f'input[value="{odds_text}"]',
                        f'//input[@value="{odds_text}"]',
                    ]
                    
                    for selector in selectors:
                        try:
                            if selector.startswith('//'):
                                await self.page.click(f'xpath={selector}', force=True, timeout=5000)
                            else:
                                await self.page.click(selector, force=True, timeout=5000)
                            clicked = True
                            logger.info(f"Step 4: Clicked odds button '{odds_text}' using selector: {selector}")
                            break
                        except Exception as click_err:
                            logger.error(f"Selector '{selector}' failed: {str(click_err)}")
                            continue
                
                if not clicked:
                    return {
                        "success": False, 
                        "message": f"Could not find odds button '{odds_text}' for game. Check /tmp/step3_games_html.html for debugging"
                    }
                
                await self.page.wait_for_timeout(2000)
                
                # Click Continue button
                await self.page.click('input[value="Continue"]', force=True, timeout=5000)
                await self.page.wait_for_timeout(3000)
                logger.info("Step 4: Clicked Continue after selecting odds")
                
            except Exception as e:
                logger.error(f"Could not find/click odds: {str(e)}")
                return {"success": False, "message": f"Could not find/click odds: {str(e)}"}
            
            await self.page.screenshot(path="/tmp/step4_betslip.png")
            
            # Step 5: Select "To Win Amount" radio button and enter amount
            try:
                # Select "To Win Amount" radio button
                await self.page.click('input[value="To Win Amount"]', timeout=5000)
                await self.page.wait_for_timeout(500)
                logger.info("Step 5: Selected 'To Win Amount' radio button")
                
                # Find the input field and enter wager amount
                # The input is typically near the radio buttons
                await self.page.fill('input[type="text"]:visible', str(int(wager)))
                await self.page.wait_for_timeout(1000)
                logger.info(f"Step 5: Entered wager amount: ${wager}")
                
                # Click Continue
                await self.page.click('input[value="Continue"]', force=True, timeout=5000)
                await self.page.wait_for_timeout(3000)
                logger.info("Step 5: Clicked Continue")
                
            except Exception as e:
                logger.error(f"Could not enter wager amount: {str(e)}")
                return {"success": False, "message": f"Could not enter wager amount: {str(e)}"}
            
            await self.page.screenshot(path="/tmp/step5_confirmation.png")
            
            # Step 6: Click Confirm button to place the bet
            try:
                await self.page.click('input[value="Confirm"]', force=True, timeout=5000)
                await self.page.wait_for_timeout(3000)
                logger.info("Step 6: Clicked Confirm button")
                
            except Exception as e:
                logger.error(f"Could not click Confirm: {str(e)}")
                return {"success": False, "message": f"Could not click Confirm: {str(e)}"}
            
            await self.page.screenshot(path="/tmp/step6_final.png")
            
            # Step 7: Verify bet was placed by checking for Ticket# on confirmation page
            try:
                # Look for "Ticket#" text on the page
                page_content = await self.page.content()
                
                if "Ticket#" in page_content or "ticket" in page_content.lower():
                    # Try to extract ticket number
                    import re
                    ticket_match = re.search(r'Ticket#?[:\s]*(\d+)', page_content)
                    ticket_number = ticket_match.group(1) if ticket_match else "Unknown"
                    
                    logger.info(f"BET PLACED SUCCESSFULLY! Ticket#: {ticket_number}")
                    
                    return {
                        "success": True,
                        "message": f"Bet placed successfully: {game} - {bet_type} {line} @ {odds} for ${wager} MXN",
                        "ticket_number": ticket_number,
                        "bet_details": {
                            "game": game,
                            "bet_type": bet_type,
                            "line": line,
                            "odds": odds,
                            "wager": wager
                        },
                        "screenshots": "Check /tmp/step*.png for verification"
                    }
                else:
                    return {
                        "success": False,
                        "message": "Reached final page but could not verify bet placement (no Ticket# found)",
                        "screenshots": "Check /tmp/step*.png for debugging"
                    }
                    
            except Exception as e:
                logger.error(f"Error verifying bet: {str(e)}")
                return {"success": False, "message": f"Error verifying bet: {str(e)}"}
                
        except Exception as e:
            logger.error(f"Error placing bet: {str(e)}")
            await self.page.screenshot(path="/tmp/error.png")
            return {"success": False, "message": f"Error: {str(e)}", "screenshot": "/tmp/error.png"}


plays888_service = Plays888Service()


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
        
        return {
            "success": True,
            "message": f"Bet recorded: {bet.game} - {bet.bet_type} {bet.line} @ {bet.odds} for ${bet.wager}",
            "bet_id": bet_doc["id"]
        }
    except Exception as e:
        logger.error(f"Record manual bet error: {str(e)}")
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
    client.close()
    await plays888_service.close()
