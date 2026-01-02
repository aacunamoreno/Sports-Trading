#!/usr/bin/env python3
"""
Data Fixes Verification Test for Betting Bot
Tests the specific data fixes made on Dec 27, 2024:
1. NHL Today - Tampa Bay @ Florida line fix (should be 6.0, not 5.5)
2. NBA Yesterday - Final scores population for all 9 games
"""

import requests
import sys
import json
from datetime import datetime

class DataFixesVerificationTester:
    def __init__(self, base_url="https://plays-dashboard.preview.emergentagent.com"):
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

    def test_nhl_today_tampa_bay_florida_line(self):
        """Test 1: NHL Today (Dec 27) - Tampa Bay @ Florida Line should be 6.0"""
        try:
            print("Testing NHL Today - Tampa Bay @ Florida line fix...")
            response = requests.get(f"{self.api_url}/opportunities/nhl?day=today", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                if not isinstance(data, dict) or 'games' not in data:
                    self.log_test("NHL Today API Structure", False, "Response missing 'games' field")
                    return False
                
                games = data.get('games', [])
                if not isinstance(games, list):
                    self.log_test("NHL Today Games Array", False, "Games is not an array")
                    return False
                
                # Find Tampa Bay @ Florida game
                tampa_bay_game = None
                for game in games:
                    away_team = game.get('away_team', '').strip()
                    home_team = game.get('home_team', '').strip()
                    
                    if away_team == 'Tampa Bay' and home_team == 'Florida':
                        tampa_bay_game = game
                        break
                
                if not tampa_bay_game:
                    self.log_test("NHL Today - Tampa Bay @ Florida Game Found", False, 
                                "Tampa Bay @ Florida game not found in today's NHL games")
                    return False
                
                # Check the total line
                actual_total = tampa_bay_game.get('total')
                expected_total = 6.0
                
                if actual_total is None:
                    self.log_test("NHL Today - Tampa Bay @ Florida Total", False,
                                "Total field is missing or null")
                    return False
                
                if actual_total != expected_total:
                    self.log_test("NHL Today - Tampa Bay @ Florida Line Fix", False,
                                f"Expected total {expected_total}, got {actual_total}. Line fix not applied correctly!")
                    return False
                
                self.log_test("NHL Today - Tampa Bay @ Florida Line Fix", True,
                            f"✅ CRITICAL FIX VERIFIED: Tampa Bay @ Florida total is {actual_total} (was 5.5)")
                return True
            else:
                self.log_test("NHL Today API", False, f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("NHL Today API", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("NHL Today API", False, f"JSON decode error: {str(e)}")
            return False

    def test_nba_yesterday_final_scores(self):
        """Test 2: NBA Yesterday (Dec 26) - Final Scores Population"""
        try:
            print("Testing NBA Yesterday - Final scores population...")
            response = requests.get(f"{self.api_url}/opportunities?day=yesterday", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                if not isinstance(data, dict) or 'games' not in data:
                    self.log_test("NBA Yesterday API Structure", False, "Response missing 'games' field")
                    return False
                
                games = data.get('games', [])
                if not isinstance(games, list):
                    self.log_test("NBA Yesterday Games Array", False, "Games is not an array")
                    return False
                
                # Expected final scores from scoresandodds.com
                expected_final_scores = {
                    ("Boston", "Indiana"): 262,
                    ("Toronto", "Washington"): 255,
                    ("Charlotte", "Orlando"): 225,
                    ("Miami", "Atlanta"): 237,
                    ("Philadelphia", "Chicago"): 211,
                    ("Milwaukee", "Memphis"): 229,
                    ("Phoenix", "New Orleans"): 223,
                    ("Detroit", "Utah"): 260,
                    ("LA Clippers", "Portland"): 222
                }
                
                # Check if we have the expected 9 games
                if len(games) != 9:
                    self.log_test("NBA Yesterday Game Count", False,
                                f"Expected 9 games, got {len(games)}")
                    return False
                
                # Track found games and their final scores
                found_games = {}
                missing_final_scores = []
                incorrect_final_scores = []
                
                for game in games:
                    away_team = game.get('away_team', '').strip()
                    home_team = game.get('home_team', '').strip()
                    final_score = game.get('final_score')
                    
                    # Check if this game matches any expected game
                    game_key = (away_team, home_team)
                    if game_key in expected_final_scores:
                        found_games[game_key] = final_score
                        expected_score = expected_final_scores[game_key]
                        
                        if final_score is None:
                            missing_final_scores.append(f"{away_team} @ {home_team}")
                        elif final_score != expected_score:
                            incorrect_final_scores.append({
                                'game': f"{away_team} @ {home_team}",
                                'expected': expected_score,
                                'actual': final_score
                            })
                
                # Check if all expected games were found
                missing_games = []
                for expected_game in expected_final_scores:
                    if expected_game not in found_games:
                        missing_games.append(f"{expected_game[0]} @ {expected_game[1]}")
                
                if missing_games:
                    self.log_test("NBA Yesterday - Missing Games", False,
                                f"Missing expected games: {missing_games}")
                    return False
                
                # Check for missing final scores
                if missing_final_scores:
                    self.log_test("NBA Yesterday - Missing Final Scores", False,
                                f"Games missing final_score: {missing_final_scores}")
                    return False
                
                # Check for incorrect final scores
                if incorrect_final_scores:
                    error_details = []
                    for error in incorrect_final_scores:
                        error_details.append(f"{error['game']}: expected {error['expected']}, got {error['actual']}")
                    
                    self.log_test("NBA Yesterday - Incorrect Final Scores", False,
                                f"Incorrect final scores: {'; '.join(error_details)}")
                    return False
                
                # All checks passed
                self.log_test("NBA Yesterday - Final Scores Population", True,
                            f"✅ All 9 games have correct final_score values populated")
                
                # Log individual game verification
                verified_games = []
                for game_key, final_score in found_games.items():
                    away, home = game_key
                    verified_games.append(f"{away} @ {home}: {final_score}")
                
                self.log_test("NBA Yesterday - Individual Game Verification", True,
                            f"Verified games: {'; '.join(verified_games)}")
                
                return True
            else:
                self.log_test("NBA Yesterday API", False, f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("NBA Yesterday API", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("NBA Yesterday API", False, f"JSON decode error: {str(e)}")
            return False

    def run_data_fixes_verification(self):
        """Run data fixes verification tests"""
        print("=" * 70)
        print("DATA FIXES VERIFICATION - DECEMBER 27, 2024")
        print("=" * 70)
        print(f"Testing API: {self.api_url}")
        print()
        
        # Test 1: NHL Today - Tampa Bay @ Florida Line Fix (PRIORITY)
        print("🏒 TEST 1: NHL TODAY - TAMPA BAY @ FLORIDA LINE FIX")
        print("-" * 50)
        print("Expected: Tampa Bay @ Florida total = 6.0 (NOT 5.5)")
        self.test_nhl_today_tampa_bay_florida_line()
        
        print()
        
        # Test 2: NBA Yesterday - Final Scores Population
        print("🏀 TEST 2: NBA YESTERDAY - FINAL SCORES POPULATION")
        print("-" * 50)
        print("Expected: All 9 games should have final_score values")
        self.test_nba_yesterday_final_scores()
        
        # Print summary
        print()
        print("=" * 70)
        print("DATA FIXES VERIFICATION SUMMARY")
        print("=" * 70)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 ALL DATA FIXES VERIFIED SUCCESSFULLY!")
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} TESTS FAILED - DATA FIXES NEED ATTENTION")
        
        return self.tests_passed == self.tests_run

def main():
    tester = DataFixesVerificationTester()
    success = tester.run_data_fixes_verification()
    
    # Save detailed results
    try:
        with open('/app/data_fixes_test_results.json', 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_tests': tester.tests_run,
                'passed_tests': tester.tests_passed,
                'success_rate': (tester.tests_passed/tester.tests_run)*100 if tester.tests_run > 0 else 0,
                'results': tester.test_results
            }, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save test results: {e}")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())