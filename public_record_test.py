#!/usr/bin/env python3
"""
Public Record Calculation Testing for BetBot Opportunities API
Tests the Public Record feature that tracks how well "public consensus picks" (>=56% consensus) perform against the spread.
"""

import requests
import sys
import json
from datetime import datetime

class PublicRecordTester:
    def __init__(self, base_url="https://bettipster.preview.emergentagent.com"):
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

    def test_public_record_update(self):
        """Test POST /api/process/update-records?start_date=2025-12-22"""
        try:
            print("Testing Public Record calculation (this may take 30-60 seconds)...")
            response = requests.post(f"{self.api_url}/process/update-records?start_date=2025-12-22", timeout=90)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['status', 'records', 'updated_at', 'start_date']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("POST /api/process/update-records - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                # Check that records contain public data
                records = data.get('records', {})
                if 'NBA' not in records:
                    self.log_test("POST /api/process/update-records - NBA Records", False,
                                "NBA records not found in response")
                    return False
                
                nba_records = records['NBA']
                if 'public' not in nba_records:
                    self.log_test("POST /api/process/update-records - NBA Public", False,
                                "NBA public records not found")
                    return False
                
                public_record = nba_records['public']
                required_public_fields = ['hits', 'misses', 'games']
                missing_public_fields = [field for field in required_public_fields if field not in public_record]
                
                if missing_public_fields:
                    self.log_test("POST /api/process/update-records - Public Fields", False,
                                f"Missing public fields: {missing_public_fields}")
                    return False
                
                hits = public_record.get('hits', 0)
                misses = public_record.get('misses', 0)
                games = public_record.get('games', [])
                
                self.log_test("POST /api/process/update-records", True,
                            f"Public records calculated: {hits}-{misses} with {len(games)} games")
                return True
            else:
                self.log_test("POST /api/process/update-records", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("POST /api/process/update-records", False, "Request timeout (>90s)")
            return False
        except requests.exceptions.RequestException as e:
            self.log_test("POST /api/process/update-records", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("POST /api/process/update-records", False, f"JSON decode error: {str(e)}")
            return False

    def test_public_record_summary(self):
        """Test GET /api/records/public-summary"""
        try:
            response = requests.get(f"{self.api_url}/records/public-summary", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                expected_leagues = ['NBA', 'NHL', 'NCAAB']
                for league in expected_leagues:
                    if league not in data:
                        self.log_test("GET /api/records/public-summary - League Missing", False,
                                    f"League {league} not found in response")
                        return False
                    
                    league_data = data[league]
                    required_fields = ['record', 'hits', 'misses']
                    missing_fields = [field for field in required_fields if field not in league_data]
                    
                    if missing_fields:
                        self.log_test("GET /api/records/public-summary - League Fields", False,
                                    f"League {league} missing fields: {missing_fields}")
                        return False
                
                # Check NBA record format
                nba_record = data['NBA']['record']
                if not isinstance(nba_record, str) or '-' not in nba_record:
                    self.log_test("GET /api/records/public-summary - Record Format", False,
                                f"NBA record format invalid: {nba_record}")
                    return False
                
                self.log_test("GET /api/records/public-summary", True,
                            f"NBA: {data['NBA']['record']}, NHL: {data['NHL']['record']}, NCAAB: {data['NCAAB']['record']}")
                return True
            else:
                self.log_test("GET /api/records/public-summary", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("GET /api/records/public-summary", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("GET /api/records/public-summary", False, f"JSON decode error: {str(e)}")
            return False

    def test_public_record_detail_nba(self):
        """Test GET /api/records/public-detail/NBA"""
        try:
            response = requests.get(f"{self.api_url}/records/public-detail/NBA", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['league', 'total_record', 'hits', 'misses', 'by_date', 'threshold', 'spread_source']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("GET /api/records/public-detail/NBA - Structure", False,
                                f"Missing fields: {missing_fields}")
                    return False
                
                # Validate threshold and spread source
                threshold = data.get('threshold')
                spread_source = data.get('spread_source')
                
                if threshold != "56%":
                    self.log_test("GET /api/records/public-detail/NBA - Threshold", False,
                                f"Expected threshold '56%', got '{threshold}'")
                    return False
                
                if spread_source != "covers.com":
                    self.log_test("GET /api/records/public-detail/NBA - Spread Source", False,
                                f"Expected spread_source 'covers.com', got '{spread_source}'")
                    return False
                
                # Check by_date structure
                by_date = data.get('by_date', {})
                if not isinstance(by_date, dict):
                    self.log_test("GET /api/records/public-detail/NBA - by_date Type", False,
                                "by_date should be a dictionary")
                    return False
                
                # Validate specific dates if they exist
                expected_dates = ['2025-12-22', '2025-12-23']
                date_results = {}
                
                for date in expected_dates:
                    if date in by_date:
                        date_data = by_date[date]
                        if 'hits' in date_data and 'misses' in date_data and 'games' in date_data:
                            hits = date_data['hits']
                            misses = date_data['misses']
                            games = date_data['games']
                            date_results[date] = f"{hits}-{misses} ({len(games)} games)"
                            
                            # Validate game structure
                            for game in games:
                                required_game_fields = ['game', 'public_pick', 'consensus_pct', 'spread', 'result']
                                missing_game_fields = [field for field in required_game_fields if field not in game]
                                
                                if missing_game_fields:
                                    self.log_test("GET /api/records/public-detail/NBA - Game Fields", False,
                                                f"Game missing fields: {missing_game_fields}")
                                    return False
                                
                                # Validate consensus percentage is >= 56%
                                consensus_pct = game.get('consensus_pct')
                                if consensus_pct and consensus_pct < 56:
                                    self.log_test("GET /api/records/public-detail/NBA - Consensus Threshold", False,
                                                f"Game has consensus {consensus_pct}% < 56%")
                                    return False
                
                self.log_test("GET /api/records/public-detail/NBA", True,
                            f"League: {data['league']}, Record: {data['total_record']}, Dates: {date_results}")
                return True
            else:
                self.log_test("GET /api/records/public-detail/NBA", False,
                            f"Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("GET /api/records/public-detail/NBA", False, f"Request error: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.log_test("GET /api/records/public-detail/NBA", False, f"JSON decode error: {str(e)}")
            return False

    def test_public_record_calculation_verification(self):
        """Test that Public Record calculations match expected results for specific dates"""
        try:
            # First ensure records are updated
            update_response = requests.post(f"{self.api_url}/process/update-records?start_date=2025-12-22", timeout=90)
            if update_response.status_code != 200:
                self.log_test("Public Record Verification - Update Failed", False,
                            f"Could not update records: {update_response.status_code}")
                return False
            
            # Get detailed breakdown
            response = requests.get(f"{self.api_url}/records/public-detail/NBA", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                by_date = data.get('by_date', {})
                
                # Expected results based on review request
                expected_results = {
                    '2025-12-22': {'hits': 2, 'misses': 1},  # Charlotte HIT, Detroit HIT, Orlando MISS
                    '2025-12-23': {'hits': 1, 'misses': 4}   # Chicago HIT, others MISS
                }
                
                verification_results = {}
                all_correct = True
                
                for date, expected in expected_results.items():
                    if date in by_date:
                        actual_hits = by_date[date].get('hits', 0)
                        actual_misses = by_date[date].get('misses', 0)
                        expected_hits = expected['hits']
                        expected_misses = expected['misses']
                        
                        if actual_hits == expected_hits and actual_misses == expected_misses:
                            verification_results[date] = f"✓ {actual_hits}-{actual_misses}"
                        else:
                            verification_results[date] = f"✗ Expected {expected_hits}-{expected_misses}, got {actual_hits}-{actual_misses}"
                            all_correct = False
                    else:
                        verification_results[date] = "✗ Date not found"
                        all_correct = False
                
                if all_correct:
                    self.log_test("Public Record Calculation Verification", True,
                                f"All dates correct: {verification_results}")
                else:
                    self.log_test("Public Record Calculation Verification", False,
                                f"Verification failed: {verification_results}")
                
                return all_correct
            else:
                self.log_test("Public Record Calculation Verification", False,
                            f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Public Record Calculation Verification", False, f"Error: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all Public Record tests"""
        print("=" * 60)
        print("PUBLIC RECORD CALCULATION TESTING - January 8, 2026")
        print("=" * 60)
        print(f"Testing API: {self.api_url}")
        print()
        
        # Run Public Record Tests
        print("📊 PUBLIC RECORD TESTS")
        print("-" * 30)
        update_success = self.test_public_record_update()
        summary_success = self.test_public_record_summary()
        detail_success = self.test_public_record_detail_nba()
        verification_success = self.test_public_record_calculation_verification()
        
        public_record_success = all([update_success, summary_success, detail_success, verification_success])
        
        # Print summary
        print()
        print("=" * 60)
        print("PUBLIC RECORD TEST SUMMARY")
        print("=" * 60)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        print("\n📊 PUBLIC RECORD TEST RESULTS:")
        print(f"Update Records API: {'✅ PASSED' if update_success else '❌ FAILED'}")
        print(f"Public Summary API: {'✅ PASSED' if summary_success else '❌ FAILED'}")
        print(f"Public Detail API: {'✅ PASSED' if detail_success else '❌ FAILED'}")
        print(f"Calculation Verification: {'✅ PASSED' if verification_success else '❌ FAILED'}")
        print(f"Overall Public Record Feature: {'✅ PASSED' if public_record_success else '❌ FAILED'}")
        
        if not public_record_success:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['details']}")
        
        return public_record_success

def main():
    tester = PublicRecordTester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/public_record_test_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'tests_run': tester.tests_run,
            'tests_passed': tester.tests_passed,
            'test_results': tester.test_results
        }, f, indent=2)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()