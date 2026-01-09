#!/usr/bin/env python3
"""
Detailed Historical Data Verification for BetBot Opportunities API
Verifies specific betting records and final scores for 12/22/2025 to 12/27/2025
"""

import requests
import json
from datetime import datetime

class DetailedHistoricalVerifier:
    def __init__(self, base_url="https://stake-tracker-4.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.results = []

    def verify_nba_date(self, date_str, expected_record):
        """Verify NBA data for a specific date with detailed analysis"""
        print(f"\n🏀 NBA {date_str} - Expected Record: {expected_record}")
        print("-" * 50)
        
        try:
            response = requests.get(f"{self.api_url}/opportunities?day={date_str}", timeout=15)
            
            if response.status_code != 200:
                print(f"❌ API Error: Status code {response.status_code}")
                return False
            
            data = response.json()
            games = data.get('games', [])
            
            print(f"📊 Total Games: {len(games)}")
            
            # Analyze user bets
            user_bet_games = [g for g in games if g.get('user_bet') == True]
            print(f"🎯 Games with User Bets: {len(user_bet_games)}")
            
            if not user_bet_games:
                print("⚠️  No user bets found")
                return expected_record == "0-0"
            
            # Count wins/losses
            won_bets = []
            lost_bets = []
            
            for game in user_bet_games:
                away = game.get('away_team', 'Unknown')
                home = game.get('home_team', 'Unknown')
                final_score = game.get('final_score')
                bet_line = game.get('bet_line')
                bet_result = game.get('bet_result')
                user_bet_hit = game.get('user_bet_hit')
                
                print(f"  • {away} @ {home}")
                print(f"    Final Score: {final_score}, Bet Line: {bet_line}")
                print(f"    Bet Result: {bet_result}, User Bet Hit: {user_bet_hit}")
                
                if bet_result == 'won':
                    won_bets.append(f"{away} @ {home}")
                elif bet_result == 'lost':
                    lost_bets.append(f"{away} @ {home}")
            
            actual_record = f"{len(won_bets)}-{len(lost_bets)}"
            print(f"\n📈 Actual Record: {actual_record}")
            
            if won_bets:
                print(f"✅ Wins ({len(won_bets)}): {', '.join(won_bets)}")
            if lost_bets:
                print(f"❌ Losses ({len(lost_bets)}): {', '.join(lost_bets)}")
            
            # Verify record matches expected
            record_match = actual_record == expected_record
            print(f"🎯 Record Match: {'✅' if record_match else '❌'} (Expected: {expected_record})")
            
            # Verify all games have final scores
            games_without_scores = [g for g in games if g.get('final_score') is None]
            scores_complete = len(games_without_scores) == 0
            print(f"📊 Final Scores Complete: {'✅' if scores_complete else '❌'}")
            
            if not scores_complete:
                print(f"   Missing scores: {len(games_without_scores)} games")
            
            success = record_match and scores_complete
            self.results.append({
                'date': date_str,
                'league': 'NBA',
                'success': success,
                'expected_record': expected_record,
                'actual_record': actual_record,
                'total_games': len(games),
                'user_bet_games': len(user_bet_games),
                'scores_complete': scores_complete
            })
            
            return success
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return False

    def verify_nhl_date(self, date_str, expected_record):
        """Verify NHL data for a specific date with detailed analysis"""
        print(f"\n🏒 NHL {date_str} - Expected Record: {expected_record}")
        print("-" * 50)
        
        try:
            response = requests.get(f"{self.api_url}/opportunities/nhl?day={date_str}", timeout=15)
            
            if response.status_code != 200:
                print(f"❌ API Error: Status code {response.status_code}")
                return False
            
            data = response.json()
            games = data.get('games', [])
            
            print(f"📊 Total Games: {len(games)}")
            
            # Analyze user bets
            user_bet_games = [g for g in games if g.get('user_bet') == True]
            print(f"🎯 Games with User Bets: {len(user_bet_games)}")
            
            if not user_bet_games:
                print("⚠️  No user bets found")
                return expected_record == "0-0"
            
            # Count wins/losses
            won_bets = []
            lost_bets = []
            
            for game in user_bet_games:
                away = game.get('away_team', 'Unknown')
                home = game.get('home_team', 'Unknown')
                final_score = game.get('final_score')
                bet_line = game.get('bet_line')
                bet_result = game.get('bet_result')
                user_bet_hit = game.get('user_bet_hit')
                
                print(f"  • {away} @ {home}")
                print(f"    Final Score: {final_score}, Bet Line: {bet_line}")
                print(f"    Bet Result: {bet_result}, User Bet Hit: {user_bet_hit}")
                
                if bet_result == 'won':
                    won_bets.append(f"{away} @ {home}")
                elif bet_result == 'lost':
                    lost_bets.append(f"{away} @ {home}")
            
            actual_record = f"{len(won_bets)}-{len(lost_bets)}"
            print(f"\n📈 Actual Record: {actual_record}")
            
            if won_bets:
                print(f"✅ Wins ({len(won_bets)}): {', '.join(won_bets)}")
            if lost_bets:
                print(f"❌ Losses ({len(lost_bets)}): {', '.join(lost_bets)}")
            
            # Verify record matches expected
            record_match = actual_record == expected_record
            print(f"🎯 Record Match: {'✅' if record_match else '❌'} (Expected: {expected_record})")
            
            # Verify all games have final scores
            games_without_scores = [g for g in games if g.get('final_score') is None]
            scores_complete = len(games_without_scores) == 0
            print(f"📊 Final Scores Complete: {'✅' if scores_complete else '❌'}")
            
            if not scores_complete:
                print(f"   Missing scores: {len(games_without_scores)} games")
            
            success = record_match and scores_complete
            self.results.append({
                'date': date_str,
                'league': 'NHL',
                'success': success,
                'expected_record': expected_record,
                'actual_record': actual_record,
                'total_games': len(games),
                'user_bet_games': len(user_bet_games),
                'scores_complete': scores_complete
            })
            
            return success
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return False

    def run_verification(self):
        """Run complete historical data verification"""
        print("=" * 70)
        print("DETAILED HISTORICAL DATA VERIFICATION")
        print("BetBot Opportunities API - 12/22/2025 to 12/27/2025")
        print("=" * 70)
        
        # Expected betting records from the review request
        nba_tests = [
            ("2025-12-22", "1-2"),
            ("2025-12-23", "4-3"), 
            ("2025-12-25", "1-1"),
            ("2025-12-26", "3-2"),
            ("2025-12-27", "2-2")
        ]
        
        nhl_tests = [
            ("2025-12-22", "0-1"),
            ("2025-12-23", "3-3"),
            ("2025-12-27", "4-1")
        ]
        
        # Run NBA tests
        nba_success = True
        for date_str, expected_record in nba_tests:
            success = self.verify_nba_date(date_str, expected_record)
            if not success:
                nba_success = False
        
        # Run NHL tests
        nhl_success = True
        for date_str, expected_record in nhl_tests:
            success = self.verify_nhl_date(date_str, expected_record)
            if not success:
                nhl_success = False
        
        # Print summary
        print("\n" + "=" * 70)
        print("VERIFICATION SUMMARY")
        print("=" * 70)
        
        print(f"🏀 NBA Results: {'✅ ALL PASSED' if nba_success else '❌ SOME FAILED'}")
        print(f"🏒 NHL Results: {'✅ ALL PASSED' if nhl_success else '❌ SOME FAILED'}")
        
        overall_success = nba_success and nhl_success
        print(f"\n🎯 Overall Result: {'✅ SUCCESS' if overall_success else '❌ FAILED'}")
        
        # Detailed results table
        print(f"\n📊 Detailed Results:")
        print(f"{'Date':<12} {'League':<6} {'Expected':<10} {'Actual':<10} {'Games':<7} {'Bets':<6} {'Status':<8}")
        print("-" * 70)
        
        for result in self.results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"{result['date']:<12} {result['league']:<6} {result['expected_record']:<10} {result['actual_record']:<10} {result['total_games']:<7} {result['user_bet_games']:<6} {status:<8}")
        
        return overall_success

def main():
    verifier = DetailedHistoricalVerifier()
    success = verifier.run_verification()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())