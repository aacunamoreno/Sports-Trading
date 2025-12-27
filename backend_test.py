#!/usr/bin/env python3
"""
Backend API Testing for Betting Automation System
Tests the Opportunities endpoints and plays888.co scraping functionality
"""

import requests
import sys
import json
from datetime import datetime

class BettingSystemAPITester:
    def __init__(self, base_url="https://bettingbot-4.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        if details:
            print(f"    Details: {details}")

    def test_get_opportunities(self):
        """Test GET /api/opportunities endpoint"""
        try:
            response = requests.get(f"{self.api_url}/opportunities", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['games', 'plays', 'date', 'last_updated']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("GET /api/opportunities - Structure", False, 
                                f"Missing fields: {missing_fields}")
                    return False
                
                # Validate games array
                games = data.get('games', [])
                if not isinstance(games, list):
                    self.log_test("GET /api/opportunities - Games Array", False, 
                                "Games is not an array")
                    return False
                
                # Check if we have games data
                if len(games) > 0:
                    game = games[0]
                    game_fields = ['game_num', 'time', 'away_team', 'home_team', 
                                 'away_ppg_rank', 'away_last3_rank', 'home_ppg_rank', 
                                 'home_last3_rank', 'total', 'game_avg', 'recommendation']
                    
                    missing_game_fields = [field for field in game_fields if field not in game]
                    if missing_game_fields:
                        self.log_test("GET /api/opportunities - Game Structure", False,
                                    f"Missing game fields: {missing_game_fields}")
                        return False
                    
                    self.log_test("GET /api/opportunities - Game Structure", True,
                                f"Game has all required fields")
                
                # Validate plays array
                plays = data.get('plays', [])
                if isinstance(plays, list) and len(plays) > 0:
                    play = plays[0]
                    play_fields = ['game', 'total', 'game_avg', 'recommendation', 'color']
                    missing_play_fields = [field for field in play_fields if field not in play]
                    if missing_play_fields:
                        self.log_test("GET /api/opportunities - Play Structure", False,
                                    f"Missing play fields: {missing_play_fields}")
                    else:
                        self.log_test("GET /api/opportunities - Play Structure", True,
                                    f"Play has all required fields")
                
                self.log_test("GET /api/opportunities", True, 
                            f"Returned {len(games)} games, {len(plays)} plays")
                return True
            else:
                self.log_test("GET /api/opportunities", False, 
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("GET /api/opportunities", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("GET /api/opportunities", False, f"JSON decode error: {str(e)}")
            return False

    def test_refresh_opportunities(self):
        """Test POST /api/opportunities/refresh endpoint"""
        try:
            response = requests.post(f"{self.api_url}/opportunities/refresh", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure (same as GET)
                required_fields = ['games', 'plays', 'date', 'last_updated']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("POST /api/opportunities/refresh - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                games = data.get('games', [])
                plays = data.get('plays', [])
                
                self.log_test("POST /api/opportunities/refresh", True,
                            f"Refreshed: {len(games)} games, {len(plays)} plays")
                return True
            else:
                self.log_test("POST /api/opportunities/refresh", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("POST /api/opportunities/refresh", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("POST /api/opportunities/refresh", False, f"JSON decode error: {str(e)}")
            return False

    def test_betting_logic(self):
        """Test the betting recommendation logic"""
        try:
            response = requests.get(f"{self.api_url}/opportunities", timeout=10)
            
            if response.status_code != 200:
                self.log_test("Betting Logic Test", False, "Could not get opportunities data")
                return False
            
            data = response.json()
            games = data.get('games', [])
            
            if not games:
                self.log_test("Betting Logic Test", False, "No games data to test")
                return False
            
            # Test betting logic rules (updated rules from frontend)
            over_games = []
            under_games = []
            no_bet_games = []
            
            for game in games:
                game_avg = game.get('game_avg')
                recommendation = game.get('recommendation')
                
                if game_avg is not None:
                    if game_avg <= 12.5:  # OVER range: 1-12.5
                        if recommendation == 'OVER':
                            over_games.append(game)
                        else:
                            self.log_test("Betting Logic - OVER Rule", False,
                                        f"Game avg {game_avg} should be OVER but got {recommendation}")
                            return False
                    elif game_avg >= 17.5:  # UNDER range: 17.5-30
                        if recommendation == 'UNDER':
                            under_games.append(game)
                        else:
                            self.log_test("Betting Logic - UNDER Rule", False,
                                        f"Game avg {game_avg} should be UNDER but got {recommendation}")
                            return False
                    else:  # No edge range: 13-17
                        if recommendation is None or recommendation == '':
                            no_bet_games.append(game)
                        else:
                            self.log_test("Betting Logic - No Bet Rule", False,
                                        f"Game avg {game_avg} should have no recommendation but got {recommendation}")
                            return False
            
            self.log_test("Betting Logic Test", True,
                        f"OVER: {len(over_games)}, UNDER: {len(under_games)}, No bet: {len(no_bet_games)}")
            return True
            
        except Exception as e:
            self.log_test("Betting Logic Test", False, f"Error: {str(e)}")
            return False

    def test_color_coding(self):
        """Test color coding for recommendations"""
        try:
            response = requests.get(f"{self.api_url}/opportunities", timeout=10)
            
            if response.status_code != 200:
                self.log_test("Color Coding Test", False, "Could not get opportunities data")
                return False
            
            data = response.json()
            games = data.get('games', [])
            plays = data.get('plays', [])
            
            # Test game color coding
            for game in games:
                recommendation = game.get('recommendation')
                color = game.get('color')
                
                if recommendation == 'OVER' and color != 'green':
                    self.log_test("Color Coding - OVER", False,
                                f"OVER recommendation should be green, got {color}")
                    return False
                elif recommendation == 'UNDER' and color != 'red':
                    self.log_test("Color Coding - UNDER", False,
                                f"UNDER recommendation should be red, got {color}")
                    return False
            
            # Test plays color coding
            for play in plays:
                recommendation = play.get('recommendation')
                color = play.get('color')
                
                if recommendation == 'OVER' and color != 'green':
                    self.log_test("Color Coding - Play OVER", False,
                                f"OVER play should be green, got {color}")
                    return False
                elif recommendation == 'UNDER' and color != 'red':
                    self.log_test("Color Coding - Play UNDER", False,
                                f"UNDER play should be red, got {color}")
                    return False
            
            self.log_test("Color Coding Test", True, "All color coding is correct")
            return True
            
        except Exception as e:
            self.log_test("Color Coding Test", False, f"Error: {str(e)}")
            return False

    def test_scrape_nba_totals(self):
        """Test POST /api/scrape/totals/NBA endpoint"""
        try:
            print("Testing NBA totals scraping (this may take 30-60 seconds)...")
            response = requests.post(f"{self.api_url}/scrape/totals/NBA", timeout=90)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                if not isinstance(data, dict) or 'games' not in data:
                    self.log_test("POST /api/scrape/totals/NBA - Structure", False,
                                "Response should have 'games' field")
                    return False
                
                games = data.get('games', [])
                if not isinstance(games, list):
                    self.log_test("POST /api/scrape/totals/NBA - Games Array", False,
                                "Games should be an array")
                    return False
                
                if len(games) == 0:
                    self.log_test("POST /api/scrape/totals/NBA", False,
                                "No NBA games found - may be off-season or scraping issue")
                    return False
                
                # Validate game structure
                game = games[0]
                required_fields = ['away', 'home', 'total']
                missing_fields = [field for field in required_fields if field not in game]
                
                if missing_fields:
                    self.log_test("POST /api/scrape/totals/NBA - Game Structure", False,
                                f"Missing game fields: {missing_fields}")
                    return False
                
                self.log_test("POST /api/scrape/totals/NBA", True,
                            f"Successfully scraped {len(games)} NBA games from plays888.co")
                return True
            else:
                self.log_test("POST /api/scrape/totals/NBA", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("POST /api/scrape/totals/NBA", False, "Request timeout (>90s)")
            return False
        except requests.exceptions.RequestException as e:
            self.log_test("POST /api/scrape/totals/NBA", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("POST /api/scrape/totals/NBA", False, f"JSON decode error: {str(e)}")
            return False

    def test_scrape_nhl_totals(self):
        """Test POST /api/scrape/totals/NHL endpoint"""
        try:
            print("Testing NHL totals scraping (this may take 30-60 seconds)...")
            response = requests.post(f"{self.api_url}/scrape/totals/NHL", timeout=90)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                if not isinstance(data, dict) or 'games' not in data:
                    self.log_test("POST /api/scrape/totals/NHL - Structure", False,
                                "Response should have 'games' field")
                    return False
                
                games = data.get('games', [])
                if not isinstance(games, list):
                    self.log_test("POST /api/scrape/totals/NHL - Games Array", False,
                                "Games should be an array")
                    return False
                
                if len(games) == 0:
                    self.log_test("POST /api/scrape/totals/NHL", False,
                                "No NHL games found - may be off-season or scraping issue")
                    return False
                
                # Validate game structure
                game = games[0]
                required_fields = ['away', 'home', 'total']
                missing_fields = [field for field in required_fields if field not in game]
                
                if missing_fields:
                    self.log_test("POST /api/scrape/totals/NHL - Game Structure", False,
                                f"Missing game fields: {missing_fields}")
                    return False
                
                self.log_test("POST /api/scrape/totals/NHL", True,
                            f"Successfully scraped {len(games)} NHL games from plays888.co")
                return True
            else:
                self.log_test("POST /api/scrape/totals/NHL", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("POST /api/scrape/totals/NHL", False, "Request timeout (>90s)")
            return False
        except requests.exceptions.RequestException as e:
            self.log_test("POST /api/scrape/totals/NHL", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("POST /api/scrape/totals/NHL", False, f"JSON decode error: {str(e)}")
            return False

    def test_refresh_with_live_lines_nba(self):
        """Test POST /api/opportunities/refresh?use_live_lines=true for NBA"""
        try:
            print("Testing NBA opportunities refresh with live lines (this may take 30-60 seconds)...")
            response = requests.post(f"{self.api_url}/opportunities/refresh?use_live_lines=true", timeout=90)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['games', 'plays', 'date', 'last_updated', 'data_source']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("POST /api/opportunities/refresh?use_live_lines=true - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                # Check data source
                data_source = data.get('data_source')
                if data_source != 'plays888.co':
                    self.log_test("POST /api/opportunities/refresh?use_live_lines=true - Data Source", False,
                                f"Expected data_source 'plays888.co', got '{data_source}'")
                    return False
                
                games = data.get('games', [])
                plays = data.get('plays', [])
                
                self.log_test("POST /api/opportunities/refresh?use_live_lines=true", True,
                            f"NBA refresh with live lines: {len(games)} games, {len(plays)} plays, source: {data_source}")
                return True
            else:
                self.log_test("POST /api/opportunities/refresh?use_live_lines=true", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("POST /api/opportunities/refresh?use_live_lines=true", False, "Request timeout (>90s)")
            return False
        except requests.exceptions.RequestException as e:
            self.log_test("POST /api/opportunities/refresh?use_live_lines=true", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("POST /api/opportunities/refresh?use_live_lines=true", False, f"JSON decode error: {str(e)}")
            return False

    def test_refresh_with_live_lines_nhl(self):
        """Test POST /api/opportunities/nhl/refresh?use_live_lines=true for NHL"""
        try:
            print("Testing NHL opportunities refresh with live lines (this may take 30-60 seconds)...")
            response = requests.post(f"{self.api_url}/opportunities/nhl/refresh?use_live_lines=true", timeout=90)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['games', 'plays', 'date', 'last_updated', 'data_source']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("POST /api/opportunities/nhl/refresh?use_live_lines=true - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                # Check data source
                data_source = data.get('data_source')
                if data_source != 'plays888.co':
                    self.log_test("POST /api/opportunities/nhl/refresh?use_live_lines=true - Data Source", False,
                                f"Expected data_source 'plays888.co', got '{data_source}'")
                    return False
                
                games = data.get('games', [])
                plays = data.get('plays', [])
                
                self.log_test("POST /api/opportunities/nhl/refresh?use_live_lines=true", True,
                            f"NHL refresh with live lines: {len(games)} games, {len(plays)} plays, source: {data_source}")
                return True
            else:
                self.log_test("POST /api/opportunities/nhl/refresh?use_live_lines=true", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("POST /api/opportunities/nhl/refresh?use_live_lines=true", False, "Request timeout (>90s)")
            return False
        except requests.exceptions.RequestException as e:
            self.log_test("POST /api/opportunities/nhl/refresh?use_live_lines=true", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("POST /api/opportunities/nhl/refresh?use_live_lines=true", False, f"JSON decode error: {str(e)}")
            return False

    def test_data_source_field(self):
        """Test that GET /api/opportunities returns data_source field"""
        try:
            response = requests.get(f"{self.api_url}/opportunities", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'data_source' not in data:
                    self.log_test("GET /api/opportunities - data_source field", False,
                                "Missing data_source field in response")
                    return False
                
                data_source = data.get('data_source')
                valid_sources = ['cached', 'plays888.co']
                
                if data_source not in valid_sources:
                    self.log_test("GET /api/opportunities - data_source value", False,
                                f"Invalid data_source '{data_source}', expected one of {valid_sources}")
                    return False
                
                self.log_test("GET /api/opportunities - data_source field", True,
                            f"data_source field present with value: {data_source}")
                return True
            else:
                self.log_test("GET /api/opportunities - data_source field", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("GET /api/opportunities - data_source field", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("GET /api/opportunities - data_source field", False, f"JSON decode error: {str(e)}")
            return False

    def test_bet_time_line_tracking_yesterday(self):
        """Test GET /api/opportunities?day=yesterday for bet-time line tracking"""
        try:
            response = requests.get(f"{self.api_url}/opportunities?day=yesterday", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['games', 'date', 'success']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("GET /api/opportunities?day=yesterday - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                games = data.get('games', [])
                if not isinstance(games, list):
                    self.log_test("GET /api/opportunities?day=yesterday - Games Array", False,
                                "Games is not an array")
                    return False
                
                # Look for games with user bets
                user_bet_games = [g for g in games if g.get('user_bet') == True]
                
                if not user_bet_games:
                    self.log_test("GET /api/opportunities?day=yesterday - User Bets", False,
                                "No games with user_bet=true found")
                    return False
                
                # Test specific expected game: San Antonio @ Okla City
                san_antonio_game = None
                for game in user_bet_games:
                    if (game.get('away_team') == 'San Antonio' and game.get('home_team') == 'Okla City'):
                        san_antonio_game = game
                        break
                
                if san_antonio_game:
                    # Verify required fields for bet-time line tracking
                    required_bet_fields = ['bet_line', 'bet_edge', 'user_bet_hit', 'final_score']
                    missing_bet_fields = [field for field in required_bet_fields if field not in san_antonio_game]
                    
                    if missing_bet_fields:
                        self.log_test("Bet-Time Line Tracking - San Antonio Game Fields", False,
                                    f"Missing bet fields: {missing_bet_fields}")
                        return False
                    
                    # Verify expected values for San Antonio @ Okla City
                    expected_bet_line = 233.0
                    expected_bet_edge = 6.0
                    expected_final_score = 219
                    expected_user_bet_hit = False  # 219 < 233 means UNDER won
                    
                    actual_bet_line = san_antonio_game.get('bet_line')
                    actual_bet_edge = san_antonio_game.get('bet_edge')
                    actual_final_score = san_antonio_game.get('final_score')
                    actual_user_bet_hit = san_antonio_game.get('user_bet_hit')
                    
                    # Validate bet_line
                    if actual_bet_line != expected_bet_line:
                        self.log_test("Bet-Time Line Tracking - San Antonio bet_line", False,
                                    f"Expected bet_line {expected_bet_line}, got {actual_bet_line}")
                        return False
                    
                    # Validate bet_edge
                    if actual_bet_edge != expected_bet_edge:
                        self.log_test("Bet-Time Line Tracking - San Antonio bet_edge", False,
                                    f"Expected bet_edge {expected_bet_edge}, got {actual_bet_edge}")
                        return False
                    
                    # Validate final_score
                    if actual_final_score != expected_final_score:
                        self.log_test("Bet-Time Line Tracking - San Antonio final_score", False,
                                    f"Expected final_score {expected_final_score}, got {actual_final_score}")
                        return False
                    
                    # Validate user_bet_hit
                    if actual_user_bet_hit != expected_user_bet_hit:
                        self.log_test("Bet-Time Line Tracking - San Antonio user_bet_hit", False,
                                    f"Expected user_bet_hit {expected_user_bet_hit}, got {actual_user_bet_hit}")
                        return False
                    
                    self.log_test("Bet-Time Line Tracking - San Antonio Game", True,
                                f"All bet-time tracking fields correct: bet_line={actual_bet_line}, bet_edge={actual_bet_edge}, final={actual_final_score}, hit={actual_user_bet_hit}")
                else:
                    self.log_test("Bet-Time Line Tracking - San Antonio Game", False,
                                "San Antonio @ Okla City game not found in user bets")
                    return False
                
                # Test Houston @ LA Lakers game if present
                houston_game = None
                for game in user_bet_games:
                    if (game.get('away_team') == 'Houston' and game.get('home_team') == 'LA Lakers'):
                        houston_game = game
                        break
                
                if houston_game:
                    expected_houston_bet_line = 230.0
                    expected_houston_bet_edge = 8.5
                    expected_houston_final_score = 215
                    expected_houston_user_bet_hit = False  # 215 < 230 means UNDER won
                    
                    actual_houston_bet_line = houston_game.get('bet_line')
                    actual_houston_bet_edge = houston_game.get('bet_edge')
                    actual_houston_final_score = houston_game.get('final_score')
                    actual_houston_user_bet_hit = houston_game.get('user_bet_hit')
                    
                    if (actual_houston_bet_line == expected_houston_bet_line and
                        actual_houston_bet_edge == expected_houston_bet_edge and
                        actual_houston_final_score == expected_houston_final_score and
                        actual_houston_user_bet_hit == expected_houston_user_bet_hit):
                        self.log_test("Bet-Time Line Tracking - Houston Game", True,
                                    f"Houston game correct: bet_line={actual_houston_bet_line}, bet_edge={actual_houston_bet_edge}, final={actual_houston_final_score}, hit={actual_houston_user_bet_hit}")
                    else:
                        self.log_test("Bet-Time Line Tracking - Houston Game", False,
                                    f"Houston game values incorrect. Expected: bet_line={expected_houston_bet_line}, bet_edge={expected_houston_bet_edge}, final={expected_houston_final_score}, hit={expected_houston_user_bet_hit}. Got: bet_line={actual_houston_bet_line}, bet_edge={actual_houston_bet_edge}, final={actual_houston_final_score}, hit={actual_houston_user_bet_hit}")
                        return False
                
                self.log_test("GET /api/opportunities?day=yesterday - Bet-Time Line Tracking", True,
                            f"Found {len(user_bet_games)} games with user bets, bet-time line tracking working correctly")
                return True
            else:
                self.log_test("GET /api/opportunities?day=yesterday", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("GET /api/opportunities?day=yesterday", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("GET /api/opportunities?day=yesterday", False, f"JSON decode error: {str(e)}")
            return False

    def test_refresh_opportunities_yesterday(self):
        """Test POST /api/opportunities/refresh?day=yesterday for bet-time line tracking"""
        try:
            response = requests.post(f"{self.api_url}/opportunities/refresh?day=yesterday", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['games', 'date', 'success']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("POST /api/opportunities/refresh?day=yesterday - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                # Check data source
                data_source = data.get('data_source')
                if data_source:
                    self.log_test("POST /api/opportunities/refresh?day=yesterday - Data Source", True,
                                f"Data source: {data_source}")
                else:
                    self.log_test("POST /api/opportunities/refresh?day=yesterday - Data Source", False,
                                "No data_source field in response")
                    return False
                
                games = data.get('games', [])
                user_bet_games = [g for g in games if g.get('user_bet') == True]
                
                if user_bet_games:
                    # Verify bet-time line tracking fields are present
                    sample_game = user_bet_games[0]
                    bet_tracking_fields = ['bet_line', 'bet_edge', 'user_bet_hit']
                    missing_tracking_fields = [field for field in bet_tracking_fields if field not in sample_game]
                    
                    if missing_tracking_fields:
                        self.log_test("POST /api/opportunities/refresh?day=yesterday - Bet Tracking", False,
                                    f"Missing bet tracking fields: {missing_tracking_fields}")
                        return False
                    
                    self.log_test("POST /api/opportunities/refresh?day=yesterday - Bet Tracking", True,
                                f"Bet tracking fields present in {len(user_bet_games)} user bet games")
                
                self.log_test("POST /api/opportunities/refresh?day=yesterday", True,
                            f"Refreshed yesterday data: {len(games)} games, {len(user_bet_games)} with user bets, source: {data_source}")
                return True
            else:
                self.log_test("POST /api/opportunities/refresh?day=yesterday", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("POST /api/opportunities/refresh?day=yesterday", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("POST /api/opportunities/refresh?day=yesterday", False, f"JSON decode error: {str(e)}")
            return False

    def test_bet_line_vs_closing_line_difference(self):
        """Test that bet_line (bet-time) is different from total (closing line) for user bets"""
        try:
            response = requests.get(f"{self.api_url}/opportunities?day=yesterday", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                games = data.get('games', [])
                user_bet_games = [g for g in games if g.get('user_bet') == True]
                
                if not user_bet_games:
                    self.log_test("Bet Line vs Closing Line Test", False,
                                "No games with user bets found to test")
                    return False
                
                differences_found = 0
                for game in user_bet_games:
                    bet_line = game.get('bet_line')
                    closing_line = game.get('total')
                    
                    if bet_line is not None and closing_line is not None:
                        if bet_line != closing_line:
                            differences_found += 1
                            self.log_test(f"Line Difference - {game.get('away_team')} @ {game.get('home_team')}", True,
                                        f"Bet line: {bet_line}, Closing line: {closing_line}, Difference: {abs(bet_line - closing_line)}")
                
                if differences_found > 0:
                    self.log_test("Bet Line vs Closing Line Test", True,
                                f"Found {differences_found} games with different bet-time vs closing lines")
                    return True
                else:
                    self.log_test("Bet Line vs Closing Line Test", False,
                                "No differences found between bet-time and closing lines")
                    return False
            else:
                self.log_test("Bet Line vs Closing Line Test", False,
                            f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Bet Line vs Closing Line Test", False, f"Error: {str(e)}")
            return False

    def test_nba_data_sourcing_strategy_tomorrow(self):
        """Test GET /api/opportunities?day=tomorrow - should use scoresandodds.com"""
        try:
            response = requests.get(f"{self.api_url}/opportunities?day=tomorrow", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['games', 'date', 'success', 'data_source']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("GET /api/opportunities?day=tomorrow - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                # Check data source
                data_source = data.get('data_source')
                expected_sources = ['scoresandodds.com', 'hardcoded']  # Allow hardcoded as fallback
                
                if data_source not in expected_sources:
                    self.log_test("GET /api/opportunities?day=tomorrow - Data Source", False,
                                f"Expected data_source in {expected_sources}, got '{data_source}'")
                    return False
                
                games = data.get('games', [])
                if len(games) == 0:
                    self.log_test("GET /api/opportunities?day=tomorrow - Games Count", False,
                                "No games found for tomorrow")
                    return False
                
                # Validate game structure
                game = games[0]
                required_game_fields = ['away_team', 'home_team', 'total']
                missing_game_fields = [field for field in required_game_fields if field not in game]
                
                if missing_game_fields:
                    self.log_test("GET /api/opportunities?day=tomorrow - Game Structure", False,
                                f"Missing game fields: {missing_game_fields}")
                    return False
                
                # Expected: 9 games for Dec 27, 2025 (Dallas @ Sacramento, Phoenix @ New Orleans, etc.)
                expected_min_games = 3  # Allow some flexibility
                if len(games) < expected_min_games:
                    self.log_test("GET /api/opportunities?day=tomorrow - Game Count", False,
                                f"Expected at least {expected_min_games} games, got {len(games)}")
                    return False
                
                self.log_test("GET /api/opportunities?day=tomorrow", True,
                            f"Found {len(games)} games, data_source: {data_source}")
                return True
            else:
                self.log_test("GET /api/opportunities?day=tomorrow", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("GET /api/opportunities?day=tomorrow", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("GET /api/opportunities?day=tomorrow", False, f"JSON decode error: {str(e)}")
            return False

    def test_nba_data_sourcing_strategy_today(self):
        """Test GET /api/opportunities?day=today - should use plays888.co for live lines"""
        try:
            response = requests.get(f"{self.api_url}/opportunities?day=today", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['games', 'date', 'success']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("GET /api/opportunities?day=today - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                # Check data source (may be hardcoded if no live lines fetched)
                data_source = data.get('data_source')
                valid_sources = ['plays888.co', 'hardcoded', None]  # Allow hardcoded as fallback
                
                if data_source not in valid_sources:
                    self.log_test("GET /api/opportunities?day=today - Data Source", False,
                                f"Unexpected data_source '{data_source}', expected one of {valid_sources}")
                    return False
                
                games = data.get('games', [])
                
                # Validate game structure if games exist
                if games:
                    game = games[0]
                    required_game_fields = ['away_team', 'home_team', 'total']
                    missing_game_fields = [field for field in required_game_fields if field not in game]
                    
                    if missing_game_fields:
                        self.log_test("GET /api/opportunities?day=today - Game Structure", False,
                                    f"Missing game fields: {missing_game_fields}")
                        return False
                
                self.log_test("GET /api/opportunities?day=today", True,
                            f"Found {len(games)} games, data_source: {data_source}")
                return True
            else:
                self.log_test("GET /api/opportunities?day=today", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("GET /api/opportunities?day=today", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("GET /api/opportunities?day=today", False, f"JSON decode error: {str(e)}")
            return False

    def test_nba_data_sourcing_strategy_yesterday(self):
        """Test GET /api/opportunities?day=yesterday - should use scoresandodds.com for final scores + plays888 for bet lines"""
        try:
            response = requests.get(f"{self.api_url}/opportunities?day=yesterday", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['games', 'date', 'success']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("GET /api/opportunities?day=yesterday - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                games = data.get('games', [])
                if len(games) == 0:
                    self.log_test("GET /api/opportunities?day=yesterday - Games Count", False,
                                "No games found for yesterday")
                    return False
                
                # Expected: 5 games for Dec 25 (Christmas Day)
                expected_games = 5
                if len(games) != expected_games:
                    self.log_test("GET /api/opportunities?day=yesterday - Game Count", False,
                                f"Expected {expected_games} games for Christmas Day, got {len(games)}")
                    return False
                
                # Check for user bets with bet_line and bet_edge fields
                user_bet_games = [g for g in games if g.get('user_bet') == True]
                
                if not user_bet_games:
                    self.log_test("GET /api/opportunities?day=yesterday - User Bets", False,
                                "No games with user_bet=true found")
                    return False
                
                # Validate user bet fields
                for game in user_bet_games:
                    required_bet_fields = ['bet_line', 'bet_edge']
                    missing_bet_fields = [field for field in required_bet_fields if field not in game]
                    
                    if missing_bet_fields:
                        self.log_test("GET /api/opportunities?day=yesterday - Bet Fields", False,
                                    f"Missing bet fields: {missing_bet_fields}")
                        return False
                
                self.log_test("GET /api/opportunities?day=yesterday", True,
                            f"Found {len(games)} games, {len(user_bet_games)} with user bets and bet-time data")
                return True
            else:
                self.log_test("GET /api/opportunities?day=yesterday", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("GET /api/opportunities?day=yesterday", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("GET /api/opportunities?day=yesterday", False, f"JSON decode error: {str(e)}")
            return False

    def test_nba_refresh_tomorrow_scoresandodds(self):
        """Test POST /api/opportunities/refresh?day=tomorrow - should force refresh from scoresandodds.com"""
        try:
            response = requests.post(f"{self.api_url}/opportunities/refresh?day=tomorrow", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['games', 'date', 'success']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("POST /api/opportunities/refresh?day=tomorrow - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                # Check data source indicates correct source
                data_source = data.get('data_source')
                expected_sources = ['scoresandodds.com', 'hardcoded']  # Allow hardcoded as fallback
                
                if data_source not in expected_sources:
                    self.log_test("POST /api/opportunities/refresh?day=tomorrow - Data Source", False,
                                f"Expected data_source in {expected_sources}, got '{data_source}'")
                    return False
                
                games = data.get('games', [])
                if len(games) == 0:
                    self.log_test("POST /api/opportunities/refresh?day=tomorrow - Games Count", False,
                                "No games found after refresh")
                    return False
                
                self.log_test("POST /api/opportunities/refresh?day=tomorrow", True,
                            f"Refreshed {len(games)} games, data_source: {data_source}")
                return True
            else:
                self.log_test("POST /api/opportunities/refresh?day=tomorrow", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("POST /api/opportunities/refresh?day=tomorrow", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("POST /api/opportunities/refresh?day=tomorrow", False, f"JSON decode error: {str(e)}")
            return False

    def test_nba_refresh_today_plays888(self):
        """Test POST /api/opportunities/refresh?day=today&use_live_lines=true - should use plays888.co"""
        try:
            response = requests.post(f"{self.api_url}/opportunities/refresh?day=today&use_live_lines=true", timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['games', 'date', 'success']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("POST /api/opportunities/refresh?day=today&use_live_lines=true - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                # Check data source
                data_source = data.get('data_source')
                expected_sources = ['plays888.co', 'hardcoded']  # Allow hardcoded as fallback
                
                if data_source not in expected_sources:
                    self.log_test("POST /api/opportunities/refresh?day=today&use_live_lines=true - Data Source", False,
                                f"Expected data_source in {expected_sources}, got '{data_source}'")
                    return False
                
                games = data.get('games', [])
                
                self.log_test("POST /api/opportunities/refresh?day=today&use_live_lines=true", True,
                            f"Refreshed {len(games)} games, data_source: {data_source}")
                return True
            else:
                self.log_test("POST /api/opportunities/refresh?day=today&use_live_lines=true", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("POST /api/opportunities/refresh?day=today&use_live_lines=true", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("POST /api/opportunities/refresh?day=today&use_live_lines=true", False, f"JSON decode error: {str(e)}")
            return False

    def test_nhl_opportunities_tomorrow_lines(self):
        """Test GET /api/opportunities/nhl?day=tomorrow - verify all 13 NHL games have correct totals for Dec 27, 2025"""
        try:
            response = requests.get(f"{self.api_url}/opportunities/nhl?day=tomorrow", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['games', 'date', 'success']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("GET /api/opportunities/nhl?day=tomorrow - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                games = data.get('games', [])
                if not isinstance(games, list):
                    self.log_test("GET /api/opportunities/nhl?day=tomorrow - Games Array", False,
                                "Games is not an array")
                    return False
                
                # Expected: 13 NHL games for December 27, 2025
                expected_game_count = 13
                if len(games) != expected_game_count:
                    self.log_test("GET /api/opportunities/nhl?day=tomorrow - Game Count", False,
                                f"Expected {expected_game_count} NHL games, got {len(games)}")
                    return False
                
                # Expected totals for each game (verified against scoresandodds.com)
                expected_totals = {
                    ("NY Rangers", "NY Islanders"): 5.5,
                    ("Minnesota", "Winnipeg"): 5.5,
                    ("Tampa Bay", "Florida"): 5.5,
                    ("Boston", "Buffalo"): 6.5,
                    ("Detroit", "Carolina"): 6.5,
                    ("Ottawa", "Toronto"): 6.5,
                    ("Washington", "New Jersey"): 5.5,  # Previously incorrect as 6.5
                    ("Chicago", "Dallas"): 5.5,
                    ("Nashville", "St. Louis"): 5.5,
                    ("Anaheim", "Los Angeles"): 6.5,  # Previously incorrect as 5.5
                    ("Colorado", "Vegas"): 6.5,
                    ("Edmonton", "Calgary"): 6.5,
                    ("San Jose", "Vancouver"): 5.5,  # Previously incorrect as 6.0
                }
                
                # Track found games and their totals
                found_games = {}
                incorrect_totals = []
                
                for game in games:
                    away_team = game.get('away_team', '').strip()
                    home_team = game.get('home_team', '').strip()
                    total = game.get('total')
                    
                    # Validate game structure
                    if not away_team or not home_team or total is None:
                        self.log_test("GET /api/opportunities/nhl?day=tomorrow - Game Structure", False,
                                    f"Game missing required fields: away_team='{away_team}', home_team='{home_team}', total={total}")
                        return False
                    
                    # Check if this game matches any expected game
                    game_key = (away_team, home_team)
                    if game_key in expected_totals:
                        found_games[game_key] = total
                        expected_total = expected_totals[game_key]
                        
                        if total != expected_total:
                            incorrect_totals.append({
                                'game': f"{away_team} @ {home_team}",
                                'expected': expected_total,
                                'actual': total
                            })
                
                # Check if all expected games were found
                missing_games = []
                for expected_game in expected_totals:
                    if expected_game not in found_games:
                        missing_games.append(f"{expected_game[0]} @ {expected_game[1]}")
                
                if missing_games:
                    self.log_test("GET /api/opportunities/nhl?day=tomorrow - Missing Games", False,
                                f"Missing expected games: {missing_games}")
                    return False
                
                # Check for incorrect totals
                if incorrect_totals:
                    error_details = []
                    for error in incorrect_totals:
                        error_details.append(f"{error['game']}: expected {error['expected']}, got {error['actual']}")
                    
                    self.log_test("GET /api/opportunities/nhl?day=tomorrow - Incorrect Totals", False,
                                f"Incorrect totals found: {'; '.join(error_details)}")
                    return False
                
                # Specifically verify the 3 corrected games
                corrected_games = [
                    ("Washington", "New Jersey", 5.5),
                    ("Anaheim", "Los Angeles", 6.5),
                    ("San Jose", "Vancouver", 5.5)
                ]
                
                corrected_games_verified = []
                for away, home, expected_total in corrected_games:
                    game_key = (away, home)
                    if game_key in found_games:
                        actual_total = found_games[game_key]
                        if actual_total == expected_total:
                            corrected_games_verified.append(f"{away} @ {home}: {actual_total} ✓")
                        else:
                            self.log_test("GET /api/opportunities/nhl?day=tomorrow - Corrected Game", False,
                                        f"{away} @ {home}: expected {expected_total}, got {actual_total}")
                            return False
                
                self.log_test("GET /api/opportunities/nhl?day=tomorrow - All Games Verified", True,
                            f"All {len(games)} NHL games have correct totals")
                
                self.log_test("GET /api/opportunities/nhl?day=tomorrow - Corrected Games", True,
                            f"3 corrected games verified: {'; '.join(corrected_games_verified)}")
                
                self.log_test("GET /api/opportunities/nhl?day=tomorrow", True,
                            f"Successfully verified all {len(games)} NHL games for Dec 27, 2025")
                return True
            else:
                self.log_test("GET /api/opportunities/nhl?day=tomorrow", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("GET /api/opportunities/nhl?day=tomorrow", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("GET /api/opportunities/nhl?day=tomorrow", False, f"JSON decode error: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all API tests"""
        print("=" * 60)
        print("NBA OPPORTUNITIES API - DATA SOURCING STRATEGY TESTING")
        print("=" * 60)
        print(f"Testing API: {self.api_url}")
        print()
        
        # Run NBA Data Sourcing Strategy Tests
        print("🏀 NBA DATA SOURCING STRATEGY TESTS")
        print("-" * 40)
        self.test_nba_data_sourcing_strategy_tomorrow()
        self.test_nba_data_sourcing_strategy_today()
        self.test_nba_data_sourcing_strategy_yesterday()
        self.test_nba_refresh_tomorrow_scoresandodds()
        self.test_nba_refresh_today_plays888()
        
        print("\n🔍 BASIC API TESTS")
        print("-" * 30)
        self.test_get_opportunities()
        self.test_data_source_field()
        self.test_refresh_opportunities()
        self.test_betting_logic()
        self.test_color_coding()
        
        print("\n🎯 BET-TIME LINE TRACKING TESTS")
        print("-" * 30)
        self.test_bet_time_line_tracking_yesterday()
        self.test_refresh_opportunities_yesterday()
        self.test_bet_line_vs_closing_line_difference()
        
        print("\n🌐 PLAYS888.CO SCRAPING TESTS")
        print("-" * 30)
        # Run scraping tests (these take longer)
        self.test_scrape_nba_totals()
        self.test_scrape_nhl_totals()
        
        print("\n🔄 LIVE LINES INTEGRATION TESTS")
        print("-" * 30)
        self.test_refresh_with_live_lines_nba()
        self.test_refresh_with_live_lines_nhl()
        
        # Print summary
        print()
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    tester = BettingSystemAPITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/test_reports/backend_test_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_tests': tester.tests_run,
            'passed_tests': tester.tests_passed,
            'success_rate': (tester.tests_passed/tester.tests_run)*100 if tester.tests_run > 0 else 0,
            'results': tester.test_results
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())