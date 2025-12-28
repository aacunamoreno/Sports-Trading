import { useEffect, useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw, TrendingUp, TrendingDown, Target, Wifi, Calendar } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Opportunities() {
  const [league, setLeague] = useState('NBA');
  const [day, setDay] = useState('today');
  const [customDate, setCustomDate] = useState('');
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [data, setData] = useState({ games: [], plays: [], date: '', last_updated: '' });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [useLiveLines, setUseLiveLines] = useState(true); // Default to using live lines
  const [bettingRecord, setBettingRecord] = useState({ hits: 0, misses: 0 });
  const [edgeRecord, setEdgeRecord] = useState({ hits: 0, misses: 0 });

  useEffect(() => {
    loadOpportunities();
  }, [league, day, customDate]);
  
  // Fetch records summary (from 12/22/25 to yesterday) when league changes
  useEffect(() => {
    const fetchRecordsSummary = async () => {
      try {
        console.log('Fetching records summary for', league);
        const res = await fetch(`${BACKEND_URL}/api/records/summary`);
        const summary = await res.json();
        console.log('Records summary:', summary);
        
        if (summary[league]) {
          // Parse betting record (e.g., "11-10")
          const bettingParts = summary[league].betting_record.split('-');
          setBettingRecord({ 
            hits: parseInt(bettingParts[0]) || 0, 
            misses: parseInt(bettingParts[1]) || 0 
          });
          
          // Parse edge record (e.g., "23-16")
          const edgeParts = summary[league].edge_record.split('-');
          setEdgeRecord({ 
            hits: parseInt(edgeParts[0]) || 0, 
            misses: parseInt(edgeParts[1]) || 0 
          });
          
          console.log(`${league} records - Betting: ${bettingParts[0]}-${bettingParts[1]}, Edge: ${edgeParts[0]}-${edgeParts[1]}`);
        }
      } catch (e) {
        console.error('Error fetching records summary:', e);
      }
    };
    fetchRecordsSummary();
  }, [league]);

  const loadOpportunities = async () => {
    setLoading(true);
    try {
      const dayParam = day === 'custom' && customDate ? customDate : day;
      const endpoint = league === 'NBA' 
        ? `/opportunities?day=${dayParam}` 
        : league === 'NHL'
          ? `/opportunities/nhl?day=${dayParam}`
          : `/opportunities/nfl?day=${dayParam}`;
      const response = await axios.get(`${API}${endpoint}`);
      setData(response.data);
    } catch (error) {
      console.error('Error loading opportunities:', error);
      toast.error('Failed to load opportunities');
    } finally {
      setLoading(false);
    }
  };

  const handleDateSelect = (e) => {
    const selectedDate = e.target.value;
    setCustomDate(selectedDate);
    setDay('custom');
    setShowDatePicker(false);
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const liveParam = day === 'today' && useLiveLines ? '&use_live_lines=true' : '';
      const endpoint = league === 'NBA' 
        ? `/opportunities/refresh?day=${day}${liveParam}` 
        : league === 'NHL'
          ? `/opportunities/nhl/refresh?day=${day}${liveParam}`
          : `/opportunities/nfl/refresh?day=${day}${liveParam}`;
      const response = await axios.post(`${API}${endpoint}`);
      setData(response.data);
      const source = response.data.data_source === 'plays888.co' ? '(from plays888.co)' : '';
      toast.success(`${league} ${day === 'tomorrow' ? 'tomorrow\'s' : 'today\'s'} opportunities refreshed! ${source}`);
    } catch (error) {
      console.error('Error refreshing:', error);
      toast.error('Failed to refresh');
    } finally {
      setRefreshing(false);
    }
  };

  // Row styles: Orange for UNDER, Blue for OVER
  const getRowStyle = (recommendation) => {
    if (recommendation === 'OVER') return 'bg-blue-500/20 border-blue-500/50';
    if (recommendation === 'UNDER') return 'bg-orange-500/20 border-orange-500/50';
    return '';
  };

  // Text styles based on recommendation
  const getTextStyle = (recommendation) => {
    if (recommendation === 'OVER') return 'text-blue-400 font-bold';
    if (recommendation === 'UNDER') return 'text-orange-400 font-bold';
    return 'text-muted-foreground';
  };

  // Edge color based on league
  // NBA: Red < 5, Green >= 5
  // NHL: Red < 0.5, Green >= 0.5
  // NFL: Red < 3, Green >= 3
  const getEdgeStyle = (edge, currentLeague = league) => {
    if (currentLeague === 'NBA') {
      if (edge >= 5) return 'text-green-400 font-bold';
      return 'text-red-400 font-bold';
    } else if (currentLeague === 'NFL') {
      if (edge >= 7) return 'text-green-400 font-bold';
      return 'text-red-400 font-bold';
    } else {
      // NHL
      if (edge >= 0.5) return 'text-green-400 font-bold';
      return 'text-red-400 font-bold';
    }
  };

  // League-specific config
  const leagueConfig = {
    NBA: {
      statLabel: 'PPG',
      combinedLabel: 'PPG Avg',
      overRange: '1-12.5',
      noEdgeRange: '13-17',
      underRange: '17.5-30',
      totalTeams: 30,
      edgeThreshold: 5
    },
    NHL: {
      statLabel: 'GPG',
      combinedLabel: 'GPG Avg',
      overRange: '1-13.5',
      noEdgeRange: '14-18',
      underRange: '18.5-32',
      totalTeams: 32,
      edgeThreshold: 0.5
    },
    NFL: {
      statLabel: 'PPG',
      combinedLabel: 'PPG Avg',
      overRange: '1-16',
      noEdgeRange: '17-20',
      underRange: '21-32',
      totalTeams: 32,
      edgeThreshold: 7
    }
  };

  const config = leagueConfig[league];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading {league} opportunities...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Records from 12/22/25 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl lg:text-4xl font-heading font-bold tracking-tight flex items-center gap-2">
            <Target className="w-8 h-8 text-primary" />
            Opportunities
          </h1>
          <p className="text-sm lg:text-base text-muted-foreground mt-1">
            {league} Over/Under analysis based on {config.statLabel} rankings
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Edge Record Badge - from 12/22/25 */}
          <div className="bg-gradient-to-r from-green-600/20 to-red-600/20 border border-primary/30 rounded-lg px-4 py-2">
            <div className="text-xs text-muted-foreground text-center">Edge Record</div>
            <div className="text-xl font-bold text-center">
              <span className="text-green-400">{edgeRecord.hits}</span>
              <span className="text-muted-foreground mx-1">-</span>
              <span className="text-red-400">{edgeRecord.misses}</span>
            </div>
            <div className="text-[10px] text-muted-foreground text-center">Since 12/22</div>
          </div>
          {/* Betting Record Badge - from 12/22/25 */}
          <div className="bg-gradient-to-r from-yellow-600/20 to-orange-600/20 border border-yellow-500/30 rounded-lg px-4 py-2">
            <div className="text-xs text-muted-foreground text-center">💰 Betting Record</div>
            <div className="text-xl font-bold text-center">
              <span className="text-green-400">{bettingRecord.hits}</span>
              <span className="text-muted-foreground mx-1">-</span>
              <span className="text-red-400">{bettingRecord.misses}</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Live Lines Toggle */}
            {day === 'today' && (
              <button
                onClick={() => setUseLiveLines(!useLiveLines)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                  useLiveLines 
                    ? 'bg-green-500/20 text-green-400 border border-green-500/50' 
                    : 'bg-muted text-muted-foreground border border-muted'
                }`}
                title={useLiveLines ? 'Using live lines from plays888.co' : 'Using cached data'}
              >
                <Wifi className={`w-4 h-4 ${useLiveLines ? 'text-green-400' : 'text-muted-foreground'}`} />
                Live Lines
              </button>
            )}
            <Button 
              onClick={handleRefresh} 
              disabled={refreshing}
              className="flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh Data
            </Button>
          </div>
        </div>
      </div>

      {/* League Tabs */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex gap-2">
          {['NBA', 'NHL', 'NFL'].map((l) => (
            <button
              key={l}
              onClick={() => setLeague(l)}
              className={`px-6 py-2 rounded-lg font-bold text-sm transition-all ${
                league === l
                  ? 'bg-primary text-primary-foreground shadow-lg'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
            >
              {l === 'NBA' ? '🏀' : l === 'NHL' ? '🏒' : '🏈'} {l}
            </button>
          ))}
        </div>
        
        <div className="h-6 w-px bg-border hidden sm:block" />
        
        {/* Day Tabs */}
        <div className="flex gap-2 items-center">
          {/* Calendar Button */}
          <div className="relative">
            <button
              onClick={() => setShowDatePicker(!showDatePicker)}
              className={`px-4 py-2 rounded-lg font-medium text-sm transition-all flex items-center gap-2 ${
                day === 'custom'
                  ? 'bg-green-600 text-white shadow-lg'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
            >
              <Calendar className="w-4 h-4" />
              {day === 'custom' && customDate ? customDate : '📅'}
            </button>
            {showDatePicker && (
              <div className="absolute top-full left-0 mt-2 z-50 bg-card border border-border rounded-lg shadow-xl p-4 min-w-[200px]">
                <label className="block text-sm text-muted-foreground mb-2">Select Date:</label>
                <input
                  type="date"
                  defaultValue={customDate || new Date(Date.now() - 86400000).toISOString().split('T')[0]}
                  onChange={handleDateSelect}
                  max={new Date().toISOString().split('T')[0]}
                  className="w-full bg-muted text-foreground px-3 py-2 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer"
                  style={{ colorScheme: 'dark' }}
                />
              </div>
            )}
          </div>
          
          {/* NFL uses Week labels, NBA/NHL use day labels */}
          {league === 'NFL' ? (
            // NFL Week selector
            <>
              {['yesterday', 'today', 'tomorrow'].map((d) => (
                <button
                  key={d}
                  onClick={() => { setDay(d); setCustomDate(''); }}
                  className={`px-4 py-2 rounded-lg font-medium text-sm transition-all ${
                    day === d
                      ? d === 'yesterday' ? 'bg-purple-600 text-white shadow-lg' : 'bg-blue-600 text-white shadow-lg'
                      : 'bg-muted text-muted-foreground hover:bg-muted/80'
                  }`}
                >
                  {d === 'yesterday' ? '📊 Week 16' : d === 'today' ? '🏈 Week 17' : '📆 Week 18'}
                </button>
              ))}
            </>
          ) : (
            // NBA/NHL day selector
            <>
              {['yesterday', 'today', 'tomorrow'].map((d) => (
                <button
                  key={d}
                  onClick={() => { setDay(d); setCustomDate(''); }}
                  className={`px-4 py-2 rounded-lg font-medium text-sm transition-all ${
                    day === d
                      ? d === 'yesterday' ? 'bg-purple-600 text-white shadow-lg' : 'bg-blue-600 text-white shadow-lg'
                      : 'bg-muted text-muted-foreground hover:bg-muted/80'
                  }`}
                >
                  {d === 'yesterday' ? '📊 Yesterday' : d === 'today' ? '📅 Today' : '📆 Tomorrow'}
                </button>
              ))}
            </>
          )}
        </div>
      </div>

      {/* Info Card */}
      <Card className="glass-card border-primary/30">
        <CardContent className="pt-4">
          <div className="flex flex-wrap gap-4 text-sm">
            <div><span className="text-muted-foreground">Date:</span> <span className="font-mono">{data.date || 'N/A'}</span></div>
            <div><span className="text-muted-foreground">Last Updated:</span> <span className="font-mono">{data.last_updated || 'N/A'}</span></div>
            <div><span className="text-muted-foreground">Games:</span> <span className="font-mono">{data.games?.length || 0}</span></div>
            {data.data_source && (
              <div>
                <span className="text-muted-foreground">Source:</span>{' '}
                <span className={`font-mono ${data.data_source === 'plays888.co' ? 'text-green-400' : 'text-yellow-400'}`}>
                  {data.data_source === 'plays888.co' ? '🔴 plays888.co (Live)' : '📁 Cached'}
                </span>
              </div>
            )}
            {(day === 'yesterday' || day === 'custom') && data.games?.length > 0 && (
              <>
                <div><span className="text-muted-foreground">Hits:</span> <span className="font-mono text-green-400">{data.games.filter(g => {
                  const edgeThreshold = league === 'NBA' ? 5 : league === 'NFL' ? 7 : 0.5;
                  return g.result_hit === true && g.edge !== null && g.edge !== undefined && Math.abs(g.edge) >= edgeThreshold;
                }).length}</span></div>
                <div><span className="text-muted-foreground">Misses:</span> <span className="font-mono text-red-400">{data.games.filter(g => {
                  const edgeThreshold = league === 'NBA' ? 5 : league === 'NFL' ? 7 : 0.5;
                  return g.result_hit === false && g.edge !== null && g.edge !== undefined && Math.abs(g.edge) >= edgeThreshold;
                }).length}</span></div>
                <div className="border-l border-border pl-4 ml-2">
                  <span className="text-muted-foreground">💰 My Bets:</span>{' '}
                  <span className="font-mono text-green-400">{data.games.filter(g => g.user_bet && g.user_bet_hit === true).length}</span>
                  <span className="text-muted-foreground">-</span>
                  <span className="font-mono text-red-400">{data.games.filter(g => g.user_bet && g.user_bet_hit === false).length}</span>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Today's Plays - only show games with active bets */}
      {day !== 'yesterday' && day !== 'custom' && data.plays && data.plays.filter(p => p.has_bet).length > 0 && (
        <Card className="glass-card neon-border">
          <CardHeader className="border-b border-border pb-4">
            <CardTitle className="text-lg flex items-center gap-2">
              🎯 {league === 'NFL' 
                ? (day === 'tomorrow' ? "WEEK 18" : "WEEK 17") + " PLAYS"
                : (day === 'tomorrow' ? "TOMORROW'S" : "TODAY'S") + " PLAYS"
              }
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="grid gap-3">
              {data.plays.filter(p => p.has_bet).map((play, idx) => (
                <div 
                  key={idx}
                  className={`p-4 rounded-lg border ${getRowStyle(play.recommendation)}`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div className="flex items-center gap-3">
                      {play.has_bet && (
                        <div className="flex items-center gap-1" title={`Active bet: ${play.bet_type}${play.bet_count > 1 ? ` (x${play.bet_count})` : ''}`}>
                          <span className="text-2xl">💰</span>
                          {play.bet_count > 1 && (
                            <span className="text-sm text-yellow-400 font-bold bg-yellow-500/20 px-1 rounded">x{play.bet_count}</span>
                          )}
                        </div>
                      )}
                      {play.recommendation === 'OVER' ? (
                        <TrendingUp className="w-6 h-6 text-blue-400" />
                      ) : (
                        <TrendingDown className="w-6 h-6 text-orange-400" />
                      )}
                      <div>
                        <div className="font-bold">{play.game}</div>
                        <div className="text-sm text-muted-foreground">
                          Line: {play.bet_line || play.total} | {config.combinedLabel}: {play.combined_ppg || play.combined_gpg || 'N/A'}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-xl font-bold ${getTextStyle(play.recommendation)}`}>
                        {play.recommendation === 'OVER' ? '⬆️' : '⬇️'} {play.recommendation}
                      </div>
                      <div className="text-sm flex items-center justify-end gap-3">
                        {play.live_edge !== undefined && play.edge !== play.live_edge && (
                          <span className="text-muted-foreground">
                            Diff vs Live: <span className={play.edge > play.live_edge ? 'text-green-400' : 'text-red-400'}>
                              {play.edge > play.live_edge ? '+' : ''}{(play.edge - play.live_edge).toFixed(1)}
                            </span>
                          </span>
                        )}
                        <span>
                          Edge: <span className={getEdgeStyle(play.edge)}>
                            {play.edge >= 0 ? '+' : ''}{play.edge}
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Games Table */}
      <Card className="glass-card neon-border">
        <CardHeader className="border-b border-border pb-4">
          <CardTitle className="text-lg">
            {league} Games Analysis - {
              league === 'NFL' 
                ? (day === 'custom' && customDate ? customDate : day === 'yesterday' ? 'Week 16 (Results)' : day === 'tomorrow' ? 'Week 18' : 'Week 17')
                : (day === 'custom' && customDate ? customDate : day === 'yesterday' ? 'Yesterday (Results)' : day === 'tomorrow' ? 'Tomorrow' : 'Today')
            }
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4 overflow-x-auto">
          {(() => {
            // Determine if we're viewing historical data (past dates with results)
            const isHistorical = day === 'yesterday' || day === 'custom';
            
            return data.games && data.games.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-2">#</th>
                  <th className="text-left py-3 px-2">Time</th>
                  <th className="text-left py-3 px-2">Away</th>
                  <th className="text-center py-3 px-1"></th>
                  <th className="text-left py-3 px-2">Home</th>
                  <th className="text-center py-3 px-2">Line</th>
                  {isHistorical && <th className="text-center py-3 px-2">Final</th>}
                  {isHistorical && <th className="text-center py-3 px-2">Diff</th>}
                  <th className="text-center py-3 px-2">{league === 'NBA' ? 'PPG' : 'GPG'} Avg</th>
                  <th className="text-center py-3 px-2">Edge</th>
                  <th className="text-center py-3 px-2">{isHistorical ? 'Result' : 'Bet'}</th>
                </tr>
              </thead>
              <tbody>
                {data.games.map((game) => {
                  // Check if edge is below threshold - if so, it's a "No Bet" game
                  const edgeThreshold = league === 'NBA' ? 5 : league === 'NFL' ? 7 : 0.5;
                  const isNoBet = game.edge === null || game.edge === undefined || Math.abs(game.edge) < edgeThreshold;
                  
                  // Calculate dot-based recommendation
                  const awaySeasonRank = game.away_ppg_rank || game.away_gpg_rank || 15;
                  const awayLast3Rank = game.away_last3_rank || 15;
                  const homeSeasonRank = game.home_ppg_rank || game.home_gpg_rank || 15;
                  const homeLast3Rank = game.home_last3_rank || 15;
                  
                  // Count dots by color using thresholds: 🟢(1-8) 🔵(9-16) 🟡(17-24) 🔴(25-32)
                  const ranks = [awaySeasonRank, awayLast3Rank, homeSeasonRank, homeLast3Rank];
                  const greens = ranks.filter(r => r <= 8).length;
                  const blues = ranks.filter(r => r > 8 && r <= 16).length;
                  const yellows = ranks.filter(r => r > 16 && r <= 24).length;
                  const reds = ranks.filter(r => r > 24).length;
                  
                  // Dot-based recommendation logic - STRICT rules
                  // CLEAR OVER: 2+ Greens OR 1 Green + 2 Blues (strong offensive signal)
                  // CLEAR UNDER: 2+ Reds OR 1 Red + 2 Yellows (strong defensive signal)
                  // MIXED: Everything else (caution)
                  let dotRecommendation = null;
                  if (greens >= 2 || (greens >= 1 && blues >= 2)) {
                    dotRecommendation = 'OVER';
                  } else if (reds >= 2 || (reds >= 1 && yellows >= 2)) {
                    dotRecommendation = 'UNDER';
                  }
                  // If dots are mixed (not clearly OVER or UNDER), it's a caution situation
                  const dotsAreMixed = dotRecommendation === null;
                  
                  // Check for conflict between dots and edge recommendation
                  const edgeRecommendation = game.recommendation;
                  // Conflict = dots clearly say one thing, edge says another
                  // OR dots are mixed but edge has a recommendation (caution)
                  const hasConflict = (dotRecommendation && edgeRecommendation && dotRecommendation !== edgeRecommendation) ||
                                     (dotsAreMixed && edgeRecommendation && !isNoBet);
                  // Clear agreement = dots and edge both say the same thing
                  const hasClearAgreement = dotRecommendation && edgeRecommendation && dotRecommendation === edgeRecommendation;
                  
                  // Row styling - no color for "No Bet" games
                  let rowStyle = '';
                  if (isHistorical) {
                    if (isNoBet) {
                      rowStyle = 'bg-gray-500/10 border-gray-500/30'; // No Bet - muted style
                    } else if (game.result_hit === true) {
                      rowStyle = 'bg-green-500/20 border-green-500/50';
                    } else if (game.result_hit === false) {
                      rowStyle = 'bg-red-500/20 border-red-500/50';
                    } else {
                      rowStyle = getRowStyle(game.recommendation);
                    }
                  } else {
                    // For today/tomorrow - check for conflict or clear agreement
                    if (isNoBet) {
                      rowStyle = '';
                    } else if (hasConflict) {
                      rowStyle = 'bg-yellow-500/20 border-yellow-500/50'; // Conflict/caution - yellow
                    } else if (hasClearAgreement) {
                      rowStyle = getRowStyle(game.recommendation); // Clear agreement - blue/orange
                    } else {
                      rowStyle = getRowStyle(game.recommendation);
                    }
                  }
                  
                  // Text styling - muted for No Bet games
                  let textStyle = '';
                  if (isHistorical) {
                    if (isNoBet) {
                      textStyle = 'text-gray-400';
                    } else if (game.result_hit === true) {
                      textStyle = 'text-green-400 font-bold';
                    } else if (game.result_hit === false) {
                      textStyle = 'text-red-400 font-bold';
                    } else {
                      textStyle = getTextStyle(game.recommendation);
                    }
                  } else {
                    // For today/tomorrow - muted text for No Bet games, yellow for conflicts
                    if (isNoBet) {
                      textStyle = 'text-muted-foreground';
                    } else if (hasConflict) {
                      textStyle = 'text-yellow-400 font-bold';
                    } else if (hasClearAgreement) {
                      textStyle = getTextStyle(game.recommendation);
                    } else {
                      textStyle = getTextStyle(game.recommendation);
                    }
                  }

                  return (
                    <tr 
                      key={game.game_num}
                      className={`border-b border-border/50 ${rowStyle} ${game.has_bet ? 'ring-2 ring-yellow-500/50' : ''}`}
                    >
                      <td className="py-3 px-2 font-mono">
                        {(game.has_bet || game.user_bet) && (
                          <span className="mr-1" title={game.has_bet ? `Active bet: ${game.bet_type}${game.bet_count > 1 ? ` (x${game.bet_count})` : ''}` : 'You bet on this game'}>
                            💰{game.bet_count > 1 && <span className="text-xs text-yellow-400 font-bold">x{game.bet_count}</span>}
                          </span>
                        )}
                        {game.game_num}
                      </td>
                      <td className="py-3 px-2 text-muted-foreground">{game.time}</td>
                      {/* Away Team with Rankings */}
                      <td className={`py-3 px-2 ${textStyle}`}>
                        <div className="flex flex-col">
                          <span className="text-xs font-mono text-blue-400/70">
                            {game.away_ppg_rank || game.away_gpg_rank}/{game.away_last3_rank}
                          </span>
                          <span className="font-medium">{game.away_team}</span>
                        </div>
                      </td>
                      {/* Colored Dots - All 4 together in the middle */}
                      <td className="py-3 px-1">
                        <div className="flex items-center justify-center gap-0.5">
                          <span className={`w-2.5 h-2.5 rounded-full ${
                            (game.away_ppg_rank || game.away_gpg_rank) <= 8 ? 'bg-green-500' :
                            (game.away_ppg_rank || game.away_gpg_rank) <= 16 ? 'bg-blue-500' :
                            (game.away_ppg_rank || game.away_gpg_rank) <= 24 ? 'bg-yellow-500' : 'bg-red-500'
                          }`}></span>
                          <span className={`w-2.5 h-2.5 rounded-full ${
                            game.away_last3_rank <= 8 ? 'bg-green-500' :
                            game.away_last3_rank <= 16 ? 'bg-blue-500' :
                            game.away_last3_rank <= 24 ? 'bg-yellow-500' : 'bg-red-500'
                          }`}></span>
                          <span className={`w-2.5 h-2.5 rounded-full ${
                            (game.home_ppg_rank || game.home_gpg_rank) <= 8 ? 'bg-green-500' :
                            (game.home_ppg_rank || game.home_gpg_rank) <= 16 ? 'bg-blue-500' :
                            (game.home_ppg_rank || game.home_gpg_rank) <= 24 ? 'bg-yellow-500' : 'bg-red-500'
                          }`}></span>
                          <span className={`w-2.5 h-2.5 rounded-full ${
                            game.home_last3_rank <= 8 ? 'bg-green-500' :
                            game.home_last3_rank <= 16 ? 'bg-blue-500' :
                            game.home_last3_rank <= 24 ? 'bg-yellow-500' : 'bg-red-500'
                          }`}></span>
                        </div>
                      </td>
                      {/* Home Team with Rankings */}
                      <td className={`py-3 px-2 ${textStyle}`}>
                        <div className="flex flex-col">
                          <span className="text-xs font-mono text-orange-400/70">
                            {game.home_ppg_rank || game.home_gpg_rank}/{game.home_last3_rank}
                          </span>
                          <span className="font-medium">{game.home_team}</span>
                        </div>
                      </td>
                      <td className={`py-3 px-2 text-center font-mono ${textStyle}`}>
                        {game.total ? (
                          <div className="flex flex-col">
                            {/* Current line */}
                            <span>{game.total}</span>
                            {/* Opening line in gray (if available) */}
                            {game.opening_line && game.opening_line !== game.total && (
                              <span className="text-xs text-gray-500">({game.opening_line})</span>
                            )}
                            {/* Show bet-time line if user bet on this game */}
                            {game.user_bet && game.bet_line && (
                              <span className="text-xs text-yellow-400 font-bold" title="Line when bet was placed">
                                🎯 {game.bet_line}
                              </span>
                            )}
                          </div>
                        ) : <span className="text-gray-500 text-xs">NO LINE</span>}
                      </td>
                      {isHistorical && (
                        <td className={`py-3 px-2 text-center font-mono ${textStyle}`}>
                          {game.final_score || '-'}
                        </td>
                      )}
                      {isHistorical && (
                        <td className="py-3 px-2 text-center font-mono">
                          {game.final_score && game.total ? (
                            <span className={game.final_score > game.total ? 'text-green-400' : 'text-red-400'}>
                              {game.final_score > game.total ? '⬆️' : '⬇️'} {game.final_score > game.total ? '+' : ''}{(game.final_score - game.total).toFixed(1)}
                            </span>
                          ) : '-'}
                        </td>
                      )}
                      <td className={`py-3 px-2 text-center font-bold ${textStyle}`}>{game.combined_ppg || game.combined_gpg || game.game_avg}</td>
                      <td className="py-3 px-2 text-center">
                        {game.edge !== null && game.edge !== undefined ? (
                          <div className="flex flex-col">
                            {/* Show bet-time edge if user bet on this game */}
                            {game.user_bet && game.bet_edge && (
                              <span className="text-xs text-yellow-400 font-bold" title="Edge when bet was placed">
                                🎯 +{game.bet_edge}
                              </span>
                            )}
                            <span className={`${getEdgeStyle(game.edge)} ${game.user_bet && game.bet_edge ? 'text-xs text-muted-foreground' : ''}`}>
                              {game.user_bet && game.bet_edge ? `(+${game.edge})` : (game.edge >= 0 ? '+' : '') + game.edge}
                            </span>
                          </div>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </td>
                      <td className="py-3 px-2 text-center">
                        {isHistorical ? (
                          // For historical dates with user bets: show user's bet result (HIT/MISS)
                          game.user_bet ? (
                            <span className={`px-2 py-1 rounded text-xs font-bold ${
                              game.user_bet_hit === true
                                ? 'bg-green-500/30 text-green-400'
                                : game.user_bet_hit === false
                                  ? 'bg-red-500/30 text-red-400'
                                  : 'bg-gray-500/30 text-gray-400'
                            }`}>
                              {game.user_bet_hit === true ? '✅ HIT' : game.user_bet_hit === false ? '❌ MISS' : '⏳ PENDING'}
                            </span>
                          ) : isNoBet ? (
                            // For historical dates without user bet and low edge: show NO BET
                            <span className="px-2 py-1 rounded text-xs font-bold bg-gray-500/20 text-gray-400">
                              ⚪ NO BET
                            </span>
                          ) : game.recommendation ? (
                            // For historical dates without user bet but with edge: show system result
                            <span className={`px-2 py-1 rounded text-xs font-bold ${
                              game.result_hit === true
                                ? 'bg-green-500/30 text-green-400'
                                : game.result_hit === false
                                  ? 'bg-red-500/30 text-red-400'
                                  : 'bg-gray-500/30 text-gray-400'
                            }`}>
                              {game.result_hit === true ? '✅ HIT' : game.result_hit === false ? '❌ MISS' : '⏳ PENDING'}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )
                        ) : isNoBet ? (
                          // For today/tomorrow: show "-" for No Bet games
                          <span className="text-muted-foreground">-</span>
                        ) : game.recommendation ? (
                          // For today/tomorrow: show OVER/UNDER recommendation only if edge meets threshold
                          <span className={`px-2 py-1 rounded text-xs font-bold ${
                            game.recommendation === 'OVER' 
                              ? 'bg-blue-500/30 text-blue-400' 
                              : 'bg-orange-500/30 text-orange-400'
                          }`}>
                            {game.recommendation === 'OVER' ? '⬆️' : '⬇️'} {game.recommendation}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <Target className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No {league} opportunities data available for {day === 'custom' && customDate ? customDate : day}.</p>
              <p className="text-sm mt-2">Click &quot;Refresh Data&quot; to load games.</p>
            </div>
          )
          })()}
        </CardContent>
      </Card>

      {/* Legend */}
      <Card className="glass-card">
        <CardContent className="pt-4">
          <div className="text-sm">
            <div className="font-bold mb-2">{league} Betting Rule:</div>
            <div className="flex flex-wrap gap-4">
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-blue-500/30 border border-blue-500/50"></span>
                <span>PPG Avg &gt; Line → <span className="text-blue-400 font-bold">OVER</span></span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-muted border border-border"></span>
                <span>PPG ≈ Line → No edge</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-orange-500/30 border border-orange-500/50"></span>
                <span>PPG Avg &lt; Line → <span className="text-orange-400 font-bold">UNDER</span></span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-gray-500/20 border border-gray-500/30"></span>
                <span className="text-gray-500">NO LINE = Not available in plays888</span>
              </div>
              <div className="flex items-center gap-2">
                <span>💰</span>
                <span className="text-yellow-400">Active bet placed (ENANO)</span>
              </div>
            </div>
            <div className="mt-3 pt-3 border-t border-border flex flex-wrap gap-4">
              <div className="flex items-center gap-2">
                <span className="text-green-400 font-bold">Edge ≥ {config.edgeThreshold}</span>
                <span className="text-muted-foreground">= Strong play</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-red-400 font-bold">Edge &lt; {config.edgeThreshold}</span>
                <span className="text-muted-foreground">= Wait for better line</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
