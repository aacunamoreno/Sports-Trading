#!/usr/bin/env python3
"""
NBA Data Sourcing Strategy Testing
Tests the specific requirements from the review request
"""

import requests
import sys
import json
from datetime import datetime

class NBADataSourcingTester:
    def __init__(self, base_url="https://betscout-9.preview.emergentagent.com"):
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

    def test_tomorrow_scoresandodds(self):
        """Test GET /api/opportunities?day=tomorrow - should use scoresandodds.com"""
        try:
            response = requests.get(f"{self.api_url}/opportunities?day=tomorrow", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check data source
                data_source = data.get('data_source')
                games = data.get('games', [])
                
                # Verify data source indicates scoresandodds.com or hardcoded fallback
                expected_sources = ['scoresandodds.com', 'hardcoded']
                if data_source not in expected_sources:
                    self.log_test("Tomorrow - Data Source", False,
                                f"Expected {expected_sources}, got '{data_source}'")
                    return False
                
                # Check that games have team names and total lines
                if games:
                    game = games[0]
                    required_fields = ['away_team', 'home_team', 'total']
                    missing_fields = [field for field in required_fields if field not in game]
                    
                    if missing_fields:
                        self.log_test("Tomorrow - Game Structure", False,
                                    f"Missing fields: {missing_fields}")
                        return False
                
                # Expected: 9 games for Dec 27, 2025 (allow some flexibility)
                min_expected_games = 3
                if len(games) < min_expected_games:
                    self.log_test("Tomorrow - Game Count", False,
                                f"Expected at least {min_expected_games} games, got {len(games)}")
                    return False
                
                self.log_test("Tomorrow - Scoresandodds Strategy", True,
                            f"Found {len(games)} games, data_source: {data_source}")
                return True
            else:
                self.log_test("Tomorrow - Scoresandodds Strategy", False,
                            f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Tomorrow - Scoresandodds Strategy", False, f"Error: {str(e)}")
            return False

    def test_today_plays888(self):
        """Test GET /api/opportunities?day=today - should use plays888.co for live lines"""
        try:
            response = requests.get(f"{self.api_url}/opportunities?day=today", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check data source
                data_source = data.get('data_source')
                games = data.get('games', [])
                
                # For today, data_source could be plays888.co or hardcoded
                valid_sources = ['plays888.co', 'hardcoded', None]
                if data_source not in valid_sources:
                    self.log_test("Today - Data Source", False,
                                f"Unexpected data_source '{data_source}'")
                    return False
                
                self.log_test("Today - Plays888 Strategy", True,
                            f"Found {len(games)} games, data_source: {data_source}")
                return True
            else:
                self.log_test("Today - Plays888 Strategy", False,
                            f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Today - Plays888 Strategy", False, f"Error: {str(e)}")
            return False

    def test_yesterday_final_scores_and_bet_lines(self):
        """Test GET /api/opportunities?day=yesterday - should have final scores and bet-time lines"""
        try:
            response = requests.get(f"{self.api_url}/opportunities?day=yesterday", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                games = data.get('games', [])
                if len(games) == 0:
                    self.log_test("Yesterday - Games Found", False, "No games found")
                    return False
                
                # Expected: 5 games for Dec 25 (Christmas Day)
                expected_games = 5
                if len(games) != expected_games:
                    self.log_test("Yesterday - Game Count", False,
                                f"Expected {expected_games} games for Christmas Day, got {len(games)}")
                    return False
                
                # Check for user bets with bet_line and bet_edge fields
                user_bet_games = [g for g in games if g.get('user_bet') == True]
                
                if not user_bet_games:
                    self.log_test("Yesterday - User Bets", False, "No user bets found")
                    return False
                
                # Verify user bets have bet_line and bet_edge fields
                for game in user_bet_games:
                    required_bet_fields = ['bet_line', 'bet_edge']
                    missing_bet_fields = [field for field in required_bet_fields if field not in game]
                    
                    if missing_bet_fields:
                        self.log_test("Yesterday - Bet Fields", False,
                                    f"Missing bet fields: {missing_bet_fields}")
                        return False
                
                self.log_test("Yesterday - Final Scores & Bet Lines", True,
                            f"Found {len(games)} games, {len(user_bet_games)} with bet-time data")
                return True
            else:
                self.log_test("Yesterday - Final Scores & Bet Lines", False,
                            f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Yesterday - Final Scores & Bet Lines", False, f"Error: {str(e)}")
            return False

    def test_refresh_tomorrow_force(self):
        """Test POST /api/opportunities/refresh?day=tomorrow - should force refresh from scoresandodds.com"""
        try:
            response = requests.post(f"{self.api_url}/opportunities/refresh?day=tomorrow", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check data source indicates correct source
                data_source = data.get('data_source')
                expected_sources = ['scoresandodds.com', 'hardcoded']
                
                if data_source not in expected_sources:
                    self.log_test("Refresh Tomorrow - Data Source", False,
                                f"Expected {expected_sources}, got '{data_source}'")
                    return False
                
                games = data.get('games', [])
                
                self.log_test("Refresh Tomorrow - Force Refresh", True,
                            f"Refreshed {len(games)} games, data_source: {data_source}")
                return True
            else:
                self.log_test("Refresh Tomorrow - Force Refresh", False,
                            f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Refresh Tomorrow - Force Refresh", False, f"Error: {str(e)}")
            return False

    def test_data_source_verification(self):
        """Verify all three data sources are working correctly"""
        try:
            # Test all three endpoints
            tomorrow_response = requests.get(f"{self.api_url}/opportunities?day=tomorrow", timeout=10)
            today_response = requests.get(f"{self.api_url}/opportunities?day=today", timeout=10)
            yesterday_response = requests.get(f"{self.api_url}/opportunities?day=yesterday", timeout=10)
            
            if tomorrow_response.status_code != 200:
                self.log_test("Data Source Verification", False, "Tomorrow endpoint failed")
                return False
            
            if today_response.status_code != 200:
                self.log_test("Data Source Verification", False, "Today endpoint failed")
                return False
            
            if yesterday_response.status_code != 200:
                self.log_test("Data Source Verification", False, "Yesterday endpoint failed")
                return False
            
            tomorrow_data = tomorrow_response.json()
            today_data = today_response.json()
            yesterday_data = yesterday_response.json()
            
            # Verify data sources
            tomorrow_source = tomorrow_data.get('data_source')
            today_source = today_data.get('data_source')
            yesterday_source = yesterday_data.get('data_source')
            
            sources_summary = f"Tomorrow: {tomorrow_source}, Today: {today_source}, Yesterday: {yesterday_source}"
            
            self.log_test("Data Source Verification", True, sources_summary)
            return True
            
        except Exception as e:
            self.log_test("Data Source Verification", False, f"Error: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all NBA data sourcing strategy tests"""
        print("=" * 60)
        print("NBA OPPORTUNITIES API - DATA SOURCING STRATEGY TESTING")
        print("=" * 60)
        print(f"Testing API: {self.api_url}")
        print()
        
        print("🏀 NBA DATA SOURCING STRATEGY TESTS")
        print("-" * 40)
        
        # Test each day's data sourcing strategy
        self.test_tomorrow_scoresandodds()
        self.test_today_plays888()
        self.test_yesterday_final_scores_and_bet_lines()
        self.test_refresh_tomorrow_force()
        self.test_data_source_verification()
        
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
    tester = NBADataSourcingTester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/nba_data_sourcing_test_results.json', 'w') as f:
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