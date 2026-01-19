#!/usr/bin/env python3
"""
NHL Opportunities API Testing for December 27, 2025
Tests specifically the NHL lines for tomorrow
"""

import requests
import sys
import json
from datetime import datetime

def test_nhl_opportunities_tomorrow():
    """Test GET /api/opportunities/nhl?day=tomorrow - verify all 13 NHL games have correct totals for Dec 27, 2025"""
    base_url = "https://betanalyst-20.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    print("🏒 Testing NHL Opportunities API for Tomorrow (December 27, 2025)")
    print("=" * 70)
    
    try:
        print("Making request to: GET /api/opportunities/nhl?day=tomorrow")
        response = requests.get(f"{api_url}/opportunities/nhl?day=tomorrow", timeout=15)
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response received successfully")
            
            # Validate response structure
            required_fields = ['games', 'date', 'success']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                print(f"❌ FAIL - Missing required fields: {missing_fields}")
                return False
            
            games = data.get('games', [])
            if not isinstance(games, list):
                print(f"❌ FAIL - Games is not an array")
                return False
            
            print(f"Found {len(games)} NHL games")
            
            # Expected: 13 NHL games for December 27, 2025
            expected_game_count = 13
            if len(games) != expected_game_count:
                print(f"❌ FAIL - Expected {expected_game_count} NHL games, got {len(games)}")
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
            
            print("\nVerifying game totals:")
            print("-" * 50)
            
            # Track found games and their totals
            found_games = {}
            incorrect_totals = []
            
            for i, game in enumerate(games, 1):
                away_team = game.get('away_team', '').strip()
                home_team = game.get('home_team', '').strip()
                total = game.get('total')
                
                print(f"{i:2d}. {away_team} @ {home_team}: {total}")
                
                # Validate game structure
                if not away_team or not home_team or total is None:
                    print(f"❌ FAIL - Game missing required fields: away_team='{away_team}', home_team='{home_team}', total={total}")
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
                        print(f"    ❌ INCORRECT: Expected {expected_total}, got {total}")
                    else:
                        print(f"    ✅ CORRECT")
                else:
                    print(f"    ⚠️  UNEXPECTED GAME (not in expected list)")
            
            # Check if all expected games were found
            missing_games = []
            for expected_game in expected_totals:
                if expected_game not in found_games:
                    missing_games.append(f"{expected_game[0]} @ {expected_game[1]}")
            
            if missing_games:
                print(f"\n❌ FAIL - Missing expected games: {missing_games}")
                return False
            
            # Check for incorrect totals
            if incorrect_totals:
                print(f"\n❌ FAIL - Incorrect totals found:")
                for error in incorrect_totals:
                    print(f"  - {error['game']}: expected {error['expected']}, got {error['actual']}")
                return False
            
            # Specifically verify the 3 corrected games
            print(f"\nVerifying the 3 corrected games:")
            print("-" * 40)
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
                        corrected_games_verified.append(f"{away} @ {home}: {actual_total}")
                        print(f"✅ {away} @ {home}: {actual_total} (corrected)")
                    else:
                        print(f"❌ {away} @ {home}: expected {expected_total}, got {actual_total}")
                        return False
            
            print(f"\n✅ SUCCESS - All {len(games)} NHL games have correct totals!")
            print(f"✅ All 3 corrected games verified: {', '.join(corrected_games_verified)}")
            return True
        else:
            print(f"❌ FAIL - HTTP Status code: {response.status_code}")
            if response.text:
                print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ FAIL - Request error: {str(e)}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ FAIL - JSON decode error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ FAIL - Unexpected error: {str(e)}")
        return False

def main():
    success = test_nhl_opportunities_tomorrow()
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 NHL OPPORTUNITIES API TEST PASSED!")
        print("All 13 games for December 27, 2025 have correct totals.")
        return 0
    else:
        print("💥 NHL OPPORTUNITIES API TEST FAILED!")
        print("Some games have incorrect totals or other issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())