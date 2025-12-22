#!/usr/bin/env python3
"""
Backend API Testing for Betting Automation System
Tests the Opportunities endpoints for NBA game analysis
"""

import requests
import sys
import json
from datetime import datetime

class OpportunitiesAPITester:
    def __init__(self, base_url="https://smart-betting-18.preview.emergentagent.com"):
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
            
            # Test betting logic rules
            over_games = []
            under_games = []
            no_bet_games = []
            
            for game in games:
                game_avg = game.get('game_avg')
                recommendation = game.get('recommendation')
                
                if game_avg is not None:
                    if game_avg <= 10:
                        if recommendation == 'OVER':
                            over_games.append(game)
                        else:
                            self.log_test("Betting Logic - OVER Rule", False,
                                        f"Game avg {game_avg} should be OVER but got {recommendation}")
                            return False
                    elif game_avg >= 21:
                        if recommendation == 'UNDER':
                            under_games.append(game)
                        else:
                            self.log_test("Betting Logic - UNDER Rule", False,
                                        f"Game avg {game_avg} should be UNDER but got {recommendation}")
                            return False
                    else:  # 11-20 range
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

    def run_all_tests(self):
        """Run all API tests"""
        print("=" * 60)
        print("BETTING AUTOMATION SYSTEM - API TESTING")
        print("=" * 60)
        print(f"Testing API: {self.api_url}")
        print()
        
        # Run tests
        self.test_get_opportunities()
        self.test_refresh_opportunities()
        self.test_betting_logic()
        self.test_color_coding()
        
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
    tester = OpportunitiesAPITester()
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