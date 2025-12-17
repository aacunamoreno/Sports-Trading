#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class BettingAPITester:
    def __init__(self, base_url="https://betautopilot-1.preview.emergentagent.com"):
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

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)

            success = response.status_code == expected_status
            
            if success:
                try:
                    response_data = response.json()
                    details = f"Status: {response.status_code}, Response: {json.dumps(response_data, indent=2)[:200]}..."
                except:
                    details = f"Status: {response.status_code}, Response: {response.text[:200]}..."
            else:
                details = f"Expected {expected_status}, got {response.status_code}. Response: {response.text[:200]}..."

            self.log_test(name, success, details)
            return success, response.json() if success and response.text else {}

        except Exception as e:
            self.log_test(name, False, f"Exception: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API Endpoint", "GET", "", 200)

    def test_connection_setup(self):
        """Test connection setup with provided credentials"""
        success, response = self.run_test(
            "Connection Setup (plays888.co login)",
            "POST",
            "connection/setup",
            200,
            data={
                "username": "jac075",
                "password": "acuna2025!"
            }
        )
        
        if success:
            # Check if login was successful
            if response.get("success"):
                self.log_test("Login Success Check", True, "Successfully connected to plays888.co")
            else:
                self.log_test("Login Success Check", False, f"Login failed: {response.get('message', 'Unknown error')}")
        
        return success

    def test_connection_status(self):
        """Test connection status endpoint"""
        return self.run_test("Connection Status", "GET", "connection/status", 200)

    def test_create_betting_rule(self):
        """Test creating a betting rule"""
        success, response = self.run_test(
            "Create Betting Rule",
            "POST",
            "rules",
            200,
            data={
                "name": "Test Soccer Rule",
                "min_odds": 1.5,
                "max_odds": 3.0,
                "wager_amount": 10.0,
                "sport": "Soccer",
                "enabled": True,
                "auto_place": False
            }
        )
        
        if success and response.get("rule_id"):
            self.created_rule_id = response["rule_id"]
            return True
        return success

    def test_get_betting_rules(self):
        """Test getting all betting rules"""
        return self.run_test("Get Betting Rules", "GET", "rules", 200)

    def test_delete_betting_rule(self):
        """Test deleting a betting rule"""
        if hasattr(self, 'created_rule_id'):
            return self.run_test(
                "Delete Betting Rule",
                "DELETE",
                f"rules/{self.created_rule_id}",
                200
            )
        else:
            self.log_test("Delete Betting Rule", False, "No rule ID available for deletion")
            return False

    def test_get_opportunities(self):
        """Test getting betting opportunities"""
        return self.run_test("Get Opportunities", "GET", "opportunities", 200)

    def test_place_bet(self):
        """Test placing a bet"""
        return self.run_test(
            "Place Bet",
            "POST",
            "bets/place",
            200,
            data={
                "opportunity_id": "test-opportunity-123",
                "wager_amount": 5.0
            }
        )

    def test_get_bet_history(self):
        """Test getting bet history"""
        return self.run_test("Get Bet History", "GET", "bets/history", 200)

    def test_get_stats(self):
        """Test getting dashboard stats"""
        return self.run_test("Get Dashboard Stats", "GET", "stats", 200)

    def run_all_tests(self):
        """Run all API tests"""
        print(f"🚀 Starting API tests for {self.base_url}")
        print("=" * 60)

        # Test basic connectivity
        self.test_root_endpoint()
        
        # Test connection setup (most important)
        self.test_connection_setup()
        
        # Test connection status
        self.test_connection_status()
        
        # Test betting rules CRUD
        self.test_create_betting_rule()
        self.test_get_betting_rules()
        
        # Test opportunities and betting
        self.test_get_opportunities()
        self.test_place_bet()
        self.test_get_bet_history()
        
        # Test dashboard stats
        self.test_get_stats()
        
        # Clean up - delete created rule
        self.test_delete_betting_rule()

        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print("⚠️  Some tests failed. Check details above.")
            return 1

def main():
    tester = BettingAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())