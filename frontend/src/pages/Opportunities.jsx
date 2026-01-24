import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw, TrendingUp, TrendingDown, Target, Wifi, Calendar, Download, Upload, Pencil, Check, X } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// NBA team nickname to city/region mapping for spread comparison
const NBA_TEAM_MAPPING = {
  'Hawks': 'Atlanta',
  'Celtics': 'Boston',
  'Nets': 'Brooklyn',
  'Hornets': 'Charlotte',
  'Bulls': 'Chicago',
  'Cavaliers': 'Cleveland',
  'Mavericks': 'Dallas',
  'Nuggets': 'Denver',
  'Pistons': 'Detroit',
  'Warriors': 'Golden State',
  'Rockets': 'Houston',
  'Pacers': 'Indiana',
  'Clippers': 'LA Clippers',
  'Lakers': 'LA Lakers',
  'Grizzlies': 'Memphis',
  'Heat': 'Miami',
  'Bucks': 'Milwaukee',
  'Timberwolves': 'Minnesota',
  'Pelicans': 'New Orleans',
  'Knicks': 'New York',
  'Thunder': 'Okla City',
  'Magic': 'Orlando',
  '76ers': 'Philadelphia',
  'Suns': 'Phoenix',
  'Trail Blazers': 'Portland',
  'Blazers': 'Portland',
  'Kings': 'Sacramento',
  'Spurs': 'San Antonio',
  'Raptors': 'Toronto',
  'Jazz': 'Utah',
  'Wizards': 'Washington',
};

// NHL team name mappings for matching bets to games
const NHL_TEAM_NAMES = {
  // Full names to short names used in bets
  'Buffalo': ['Buffalo', 'Sabres', 'BUF'],
  'NY Islanders': ['New York Islanders', 'Islanders', 'NYI'],
  'Utah': ['Utah', 'Utah Hockey Club', 'UTA'],
  'Nashville': ['Nashville', 'Predators', 'NSH'],
  'Carolina': ['Carolina', 'Hurricanes', 'CAR'],
  'Ottawa': ['Ottawa', 'Senators', 'OTT'],
  'Detroit': ['Detroit', 'Red Wings', 'DET'],
  'Winnipeg': ['Winnipeg', 'Jets', 'WPG'],
  'Montreal': ['Montreal', 'Canadiens', 'MTL'],
  'Boston': ['Boston', 'Bruins', 'BOS'],
  'Tampa Bay': ['Tampa Bay', 'Lightning', 'TBL', 'TB'],
  'Columbus': ['Columbus', 'Blue Jackets', 'CBJ'],
  'LA Kings': ['Los Angeles', 'LA Kings', 'Kings', 'LAK'],
  'St. Louis': ['St. Louis', 'Blues', 'STL'],
  'Florida': ['Florida', 'Panthers', 'FLA'],
  'Minnesota': ['Minnesota', 'Wild', 'MIN'],
  'NY Rangers': ['New York Rangers', 'Rangers', 'NYR'],
  'New Jersey': ['New Jersey', 'Devils', 'NJD'],
  'Vancouver': ['Vancouver', 'Canucks', 'VAN'],
  'Chicago': ['Chicago', 'Blackhawks', 'CHI'],
  'Dallas': ['Dallas', 'Stars', 'DAL'],
  'Washington': ['Washington', 'Capitals', 'WSH'],
  'Calgary': ['Calgary', 'Flames', 'CGY'],
  'Edmonton': ['Edmonton', 'Oilers', 'EDM'],
  'Pittsburgh': ['Pittsburgh', 'Penguins', 'PIT'],
  'Philadelphia': ['Philadelphia', 'Flyers', 'PHI'],
  'Seattle': ['Seattle', 'Kraken', 'SEA'],
  'San Jose': ['San Jose', 'Sharks', 'SJS'],
  'Anaheim': ['Anaheim', 'Ducks', 'ANA'],
  'Colorado': ['Colorado', 'Avalanche', 'COL'],
  'Vegas': ['Vegas', 'Golden Knights', 'VGK'],
  'Toronto': ['Toronto', 'Maple Leafs', 'TOR'],
  'Arizona': ['Arizona', 'Coyotes', 'ARI'],
};

// Helper function to find 1st Period bets for a specific game
const findFirstPeriodBetsForGame = (game, firstPeriodBets, gameDate) => {
  if (!firstPeriodBets?.bets || !game) return null;
  
  const awayTeam = game.away_team || game.away || '';
  const homeTeam = game.home_team || game.home || '';
  
  // Get all possible name variations for both teams
  const getTeamVariations = (teamName) => {
    const variations = [teamName.toLowerCase()];
    for (const [key, aliases] of Object.entries(NHL_TEAM_NAMES)) {
      if (key.toLowerCase() === teamName.toLowerCase() || 
          aliases.some(a => a.toLowerCase() === teamName.toLowerCase())) {
        variations.push(key.toLowerCase());
        aliases.forEach(a => variations.push(a.toLowerCase()));
      }
    }
    return [...new Set(variations)];
  };
  
  const awayVariations = getTeamVariations(awayTeam);
  const homeVariations = getTeamVariations(homeTeam);
  
  // Format the game date to match bet date format (MM/DD)
  let formattedDate = '';
  if (gameDate) {
    const dateParts = gameDate.split('-');
    if (dateParts.length === 3) {
      formattedDate = `${dateParts[1]}/${dateParts[2]}`;
    }
  }
  
  // Find matching bet
  const matchingBet = firstPeriodBets.bets.find(bet => {
    // Check date match if we have a formatted date
    if (formattedDate && bet.date && !bet.date.includes(formattedDate.replace(/^0/, ''))) {
      // Allow partial match (e.g., "01/24" matches "1/24")
      const betDateNormalized = bet.date.replace(/^0/, '');
      const gameDateNormalized = formattedDate.replace(/^0/, '');
      if (betDateNormalized !== gameDateNormalized) {
        return false;
      }
    }
    
    const betGame = (bet.game || '').toLowerCase();
    
    // Check if both teams are mentioned in the bet game string
    const hasAway = awayVariations.some(v => betGame.includes(v));
    const hasHome = homeVariations.some(v => betGame.includes(v));
    
    return hasAway && hasHome;
  });
  
  return matchingBet;
};

// Helper function to check if spread_team belongs to home team
const isSpreadTeamHome = (spreadTeam, homeTeam, awayTeam) => {
  if (!spreadTeam) return true; // Default to home if no spread_team
  
  // Direct match
  if (spreadTeam === homeTeam) return true;
  if (spreadTeam === awayTeam) return false;
  
  // Check if spread_team is a nickname that maps to home_team
  const mappedCity = NBA_TEAM_MAPPING[spreadTeam];
  if (mappedCity) {
    if (mappedCity === homeTeam || homeTeam.includes(mappedCity) || mappedCity.includes(homeTeam)) return true;
    if (mappedCity === awayTeam || awayTeam.includes(mappedCity) || mappedCity.includes(awayTeam)) return false;
  }
  
  // Fallback: check if names contain each other
  if (homeTeam.toLowerCase().includes(spreadTeam.toLowerCase()) || 
      spreadTeam.toLowerCase().includes(homeTeam.toLowerCase())) return true;
  if (awayTeam.toLowerCase().includes(spreadTeam.toLowerCase()) || 
      spreadTeam.toLowerCase().includes(awayTeam.toLowerCase())) return false;
  
  return true; // Default to home
};

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
  const [exporting, setExporting] = useState(false);
  const [edgeRecord, setEdgeRecord] = useState({ hits: 0, misses: 0, over: '0-0', under: '0-0' });
  const [updatingPPG, setUpdatingPPG] = useState(false);
  const [updatingScores, setUpdatingScores] = useState(false);
  const [updatingBetResults, setUpdatingBetResults] = useState(false);
  const [updatingRecords, setUpdatingRecords] = useState(false);
  const [rankingPPGRecord, setRankingPPGRecord] = useState({ high: { hits: 0, misses: 0 }, low: { hits: 0, misses: 0 } });
  const [publicRecord, setPublicRecord] = useState({ hits: 0, misses: 0 });
  const [publicThreshold, setPublicThreshold] = useState(57);
  const [loadingPublicRecord, setLoadingPublicRecord] = useState(false);
  const [firstPeriodZeros, setFirstPeriodZeros] = useState({ total: 0, l3: 0, l5: 0, lastUpdated: null });
  const [firstPeriodStats, setFirstPeriodStats] = useState({ pct03: 0, l3Pct: 0, l5Pct: 0 }); // Stats for 0-3 goals
  const [showFirstPeriodModal, setShowFirstPeriodModal] = useState(false);
  const [firstPeriodBreakdown, setFirstPeriodBreakdown] = useState([]);
  const [teams4Goals, setTeams4Goals] = useState([]);
  const [teams5Goals, setTeams5Goals] = useState([]);
  const [expanded4Goals, setExpanded4Goals] = useState(false);
  const [expanded5Goals, setExpanded5Goals] = useState(false);
  const [loadingFirstPeriodBreakdown, setLoadingFirstPeriodBreakdown] = useState(false);
  // 1st Period Bets tracking
  const [showFirstPeriodBetsModal, setShowFirstPeriodBetsModal] = useState(false);
  const [firstPeriodBets, setFirstPeriodBets] = useState({ bets: [], summary: {} });
  const [loadingFirstPeriodBets, setLoadingFirstPeriodBets] = useState(false);
  const [editingLine, setEditingLine] = useState(null); // { gameIndex: number, value: string }
  const [savingLine, setSavingLine] = useState(false);
  const [showCompoundModal, setShowCompoundModal] = useState(false);
  const [compoundRecords, setCompoundRecords] = useState([]);
  const [loadingCompound, setLoadingCompound] = useState(false);
  // NFL week selector state
  const [nflWeeks, setNflWeeks] = useState([]);
  const [selectedNflWeek, setSelectedNflWeek] = useState(null);
  const [showWeekPicker, setShowWeekPicker] = useState(false);

  // Fetch compound public records for the modal
  const fetchCompoundRecords = async () => {
    setLoadingCompound(true);
    try {
      const response = await axios.get(`${API}/records/public-compound/${league}`);
      setCompoundRecords(response.data.compound_records || []);
    } catch (error) {
      console.error('Error fetching compound records:', error);
      toast.error('Failed to load compound records');
    } finally {
      setLoadingCompound(false);
    }
  };

  // Fetch public record when threshold changes
  const fetchPublicRecordByThreshold = async (threshold) => {
    setLoadingPublicRecord(true);
    try {
      const response = await axios.get(`${API}/records/public-by-threshold/${league}?threshold=${threshold}`);
      setPublicRecord({
        hits: response.data.hits,
        misses: response.data.misses,
        winPct: response.data.win_pct
      });
    } catch (error) {
      console.error('Error fetching public record:', error);
    } finally {
      setLoadingPublicRecord(false);
    }
  };

  // Update public record when threshold or league changes
  useEffect(() => {
    fetchPublicRecordByThreshold(publicThreshold);
  }, [publicThreshold, league]);

  // Fetch compound records when modal opens
  useEffect(() => {
    if (showCompoundModal) {
      fetchCompoundRecords();
    }
  }, [showCompoundModal, league]);

  // Fetch NFL weeks when league is NFL
  useEffect(() => {
    if (league === 'NFL') {
      fetchNflWeeks();
    }
  }, [league]);

  const fetchNflWeeks = async () => {
    try {
      const response = await axios.get(`${API}/opportunities/nfl/weeks`);
      setNflWeeks(response.data.weeks || []);
      // Set most recent week as default if not already set
      if (!selectedNflWeek && response.data.weeks?.length > 0) {
        setSelectedNflWeek(response.data.weeks[response.data.weeks.length - 1].week);
      }
    } catch (error) {
      console.error('Error fetching NFL weeks:', error);
    }
  };

  useEffect(() => {
    loadOpportunities();
  }, [league, day, customDate, selectedNflWeek]);
  
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
            misses: parseInt(edgeParts[1]) || 0,
            over: summary[league].edge_over || '0-0',
            under: summary[league].edge_under || '0-0'
          });
          
          console.log(`${league} records - Betting: ${bettingParts[0]}-${bettingParts[1]}, Edge: ${edgeParts[0]}-${edgeParts[1]}, Over: ${summary[league].edge_over}, Under: ${summary[league].edge_under}`);
        }
      } catch (e) {
        console.error('Error fetching records summary:', e);
      }
    };
    fetchRecordsSummary();
  }, [league]);

  // Fetch Ranking PPG records when league changes
  useEffect(() => {
    const fetchRankingPPGRecords = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/records/ranking-ppg-summary`);
        const summary = await res.json();
        
        if (summary[league]) {
          setRankingPPGRecord({
            high: { hits: summary[league].high_hits, misses: summary[league].high_misses },
            low: { hits: summary[league].low_hits, misses: summary[league].low_misses }
          });
        }
      } catch (e) {
        console.error('Error fetching ranking PPG records:', e);
      }
    };
    fetchRankingPPGRecords();
  }, [league]);

  // Note: Public record is now fetched by fetchPublicRecordByThreshold (lines 35-54)
  // which uses the dynamic threshold endpoint for accurate full-season data

  // Fetch NHL 1st Period 0-3 stats when league is NHL
  useEffect(() => {
    const fetchFirstPeriodStats = async () => {
      if (league !== 'NHL') return;
      
      try {
        // Fetch breakdown to calculate 0-3 percentage
        const res = await fetch(`${BACKEND_URL}/api/nhl/first-period-breakdown`);
        const data = await res.json();
        const breakdown = data.breakdown || [];
        
        // Calculate 0-3 goals stats
        const group03 = breakdown.filter(r => r.goals <= 3);
        const group45 = breakdown.filter(r => r.goals >= 4);
        
        const total03 = group03.reduce((sum, r) => sum + r.total, 0);
        const l3_03 = group03.reduce((sum, r) => sum + r.l3, 0);
        const l5_03 = group03.reduce((sum, r) => sum + r.l5, 0);
        
        const total45 = group45.reduce((sum, r) => sum + r.total, 0);
        const l3_45 = group45.reduce((sum, r) => sum + r.l3, 0);
        const l5_45 = group45.reduce((sum, r) => sum + r.l5, 0);
        
        const grandTotal = total03 + total45;
        const l3Total = l3_03 + l3_45;
        const l5Total = l5_03 + l5_45;
        
        const pct03 = grandTotal > 0 ? ((total03 / grandTotal) * 100).toFixed(1) : 0;
        const l3Pct = l3Total > 0 ? ((l3_03 / l3Total) * 100).toFixed(1) : 0;
        const l5Pct = l5Total > 0 ? ((l5_03 / l5Total) * 100).toFixed(1) : 0;
        
        setFirstPeriodStats({
          pct03: pct03,
          l3Pct: l3Pct,
          l5Pct: l5Pct,
          l3Games: l3_03,
          l5Games: l5_03,
          l3Total: l3Total,
          l5Total: l5Total
        });
        
        // Also store breakdown for modal
        setFirstPeriodBreakdown(breakdown);
        setTeams4Goals(data.teams_4_goals || []);
        setTeams5Goals(data.teams_5_goals || []);
      } catch (e) {
        console.error('Error fetching 1st Period stats:', e);
      }
    };
    fetchFirstPeriodStats();
  }, [league]);

  // Fetch 1st Period breakdown when modal opens (only if not already loaded)
  useEffect(() => {
    const fetchFirstPeriodBreakdown = async () => {
      if (!showFirstPeriodModal) return;
      if (firstPeriodBreakdown.length > 0) return; // Already loaded
      
      setLoadingFirstPeriodBreakdown(true);
      try {
        const res = await fetch(`${BACKEND_URL}/api/nhl/first-period-breakdown`);
        const data = await res.json();
        setFirstPeriodBreakdown(data.breakdown || []);
        setTeams4Goals(data.teams_4_goals || []);
        setTeams5Goals(data.teams_5_goals || []);
      } catch (e) {
        console.error('Error fetching 1st Period breakdown:', e);
      } finally {
        setLoadingFirstPeriodBreakdown(false);
      }
    };
    fetchFirstPeriodBreakdown();
  }, [showFirstPeriodModal, firstPeriodBreakdown.length]);

  // Fetch 1st Period Bets when modal opens
  useEffect(() => {
    const fetchFirstPeriodBets = async () => {
      if (!showFirstPeriodBetsModal) return;
      
      setLoadingFirstPeriodBets(true);
      try {
        const res = await fetch(`${BACKEND_URL}/api/nhl/first-period-bets`);
        const data = await res.json();
        setFirstPeriodBets({
          bets: data.bets || [],
          summary: data.summary || {}
        });
      } catch (e) {
        console.error('Error fetching 1st Period bets:', e);
      } finally {
        setLoadingFirstPeriodBets(false);
      }
    };
    fetchFirstPeriodBets();
  }, [showFirstPeriodBetsModal]);

  // Also fetch 1st Period Bets summary for the badge when on NHL
  useEffect(() => {
    const fetchFirstPeriodBetsSummary = async () => {
      if (league !== 'NHL') return;
      
      try {
        const res = await fetch(`${BACKEND_URL}/api/nhl/first-period-bets`);
        const data = await res.json();
        setFirstPeriodBets({
          bets: data.bets || [],
          summary: data.summary || {}
        });
      } catch (e) {
        console.error('Error fetching 1st Period bets summary:', e);
      }
    };
    fetchFirstPeriodBetsSummary();
  }, [league]);

  const loadOpportunities = async () => {
    setLoading(true);
    try {
      const dayParam = day === 'custom' && customDate ? customDate : day;
      let endpoint;
      if (league === 'NBA') {
        endpoint = `/opportunities?day=${dayParam}`;
      } else if (league === 'NHL') {
        endpoint = `/opportunities/nhl?day=${dayParam}`;
      } else if (league === 'NCAAB') {
        endpoint = `/opportunities/ncaab?day=${dayParam}`;
      } else if (league === 'NFL') {
        // NFL uses week selection instead of day
        if (selectedNflWeek) {
          endpoint = `/opportunities/nfl/week/${selectedNflWeek}`;
        } else {
          endpoint = `/opportunities/nfl?day=${dayParam}`;
        }
      }
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

  const handleNflWeekSelect = (week) => {
    setSelectedNflWeek(week);
    setShowWeekPicker(false);
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    toast.info('Refreshing lines & bets from plays888.co...');
    try {
      // Use the "refresh lines & bets" endpoint that preserves PPG values and opening lines
      // Pass the current day parameter so tomorrow's games get refreshed correctly
      const response = await axios.post(`${API}/opportunities/refresh-lines?league=${league}&day=${day}`, {}, { timeout: 60000 });
      
      // For NHL, also refresh 1st Period bets (includes Open Bets for pending wagers)
      if (league === 'NHL') {
        try {
          await axios.post(`${API}/nhl/first-period-bets/refresh`, {}, { timeout: 120000 });
          // Reload first period bets data
          const fpResponse = await axios.get(`${API}/nhl/first-period-bets`);
          if (fpResponse.data) {
            setFirstPeriodBets(fpResponse.data);
          }
        } catch (fpError) {
          console.error('Error refreshing 1st Period bets:', fpError);
        }
      }
      
      // Reload data to show updates
      await loadOpportunities();
      
      const linesUpdated = response.data.lines_updated || 0;
      const betsAdded = response.data.bets_added || 0;
      const betsSkipped = response.data.bets_skipped_duplicates || 0;
      
      let message = `${league} refreshed! ${linesUpdated} line(s) updated`;
      if (betsAdded > 0) {
        message += `, ${betsAdded} bet(s) added`;
      }
      if (betsSkipped > 0) {
        message += ` (${betsSkipped} duplicates skipped)`;
      }
      
      toast.success(message);
    } catch (error) {
      console.error('Error refreshing lines & bets:', error);
      toast.error('Failed to refresh lines & bets');
    } finally {
      setRefreshing(false);
    }
  };

  // Handle NCAAB PPG Update from CBS Sports Last 3 scores
  const handleNCAABPPGUpdate = async () => {
    setUpdatingPPG(true);
    toast.info('Updating NCAAB PPG from CBS Sports... This may take a few minutes.');
    try {
      // Get tomorrow's date for the API call
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const targetDate = tomorrow.toISOString().split('T')[0];
      
      const response = await axios.post(`${API}/opportunities/ncaab/update-ppg?target_date=${targetDate}`, {}, { timeout: 300000 });
      if (response.data.success) {
        toast.success(`Updated PPG for ${response.data.games_with_ppg} of ${response.data.games_count} NCAAB games`);
        // Reload data to show updated PPG
        await loadOpportunities();
      } else {
        toast.error('Failed to update NCAAB PPG');
      }
    } catch (error) {
      console.error('Error updating NCAAB PPG:', error);
      if (error.code === 'ECONNABORTED') {
        toast.warning('PPG update is still running in background. Refresh in a few minutes.');
      } else {
        toast.error('Failed to update NCAAB PPG');
      }
    } finally {
      setUpdatingPPG(false);
    }
  };

  // Update scores for the currently viewed date from CBS Sports
  const handleUpdateScores = async () => {
    setUpdatingScores(true);
    toast.info('Fetching scores from CBS Sports...');
    try {
      // Get the date we're currently viewing from the loaded data
      // This ensures we update the exact date shown in the UI
      let dateStr;
      if (data && data.date) {
        // Use the date from the currently loaded data
        dateStr = data.date;
      } else if (day === 'yesterday') {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        dateStr = yesterday.toISOString().split('T')[0];
      } else if (day === 'today') {
        dateStr = new Date().toISOString().split('T')[0];
      } else if (day === 'tomorrow') {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        dateStr = tomorrow.toISOString().split('T')[0];
      } else if (customDate) {
        dateStr = customDate;
      } else {
        // Default to yesterday
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        dateStr = yesterday.toISOString().split('T')[0];
      }
      
      const endpoint = league === 'NBA' ? `/scores/nba/update?date=${dateStr}` 
                     : league === 'NHL' ? `/scores/nhl/update?date=${dateStr}`
                     : league === 'NFL' ? `/scores/nfl/update?date=${dateStr}`
                     : `/scores/ncaab/update?date=${dateStr}`;
      
      const response = await axios.post(`${API}${endpoint}`, {}, { timeout: 120000 });
      
      if (response.data.success) {
        toast.success(`Updated ${response.data.games_updated} games for ${dateStr}. Hit Rate: ${response.data.hit_rate}`);
        // Reload data to show updated scores
        await loadOpportunities();
        
        // Also refresh NHL 1st Period 0-0 data
        if (league === 'NHL') {
          try {
            await axios.post(`${API}/nhl/first-period-zeros/refresh`, {}, { timeout: 180000 });
            const zpRes = await axios.get(`${API}/nhl/first-period-zeros`);
            setFirstPeriodZeros({
              total: zpRes.data.total_games || 0,
              l3: zpRes.data.l3_days || 0,
              l5: zpRes.data.l5_days || 0,
              lastUpdated: zpRes.data.last_updated
            });
            toast.success('1st Period 0-0 data updated');
          } catch (e) {
            console.error('Error refreshing 1st Period 0-0:', e);
          }
        }
      } else {
        toast.error('Failed to update scores');
      }
    } catch (error) {
      console.error('Error updating scores:', error);
      toast.error('Failed to update scores. Check if scores are available.');
    } finally {
      setUpdatingScores(false);
    }
  };

  // Update bet results from plays888.co History
  const handleUpdateBetResults = async () => {
    setUpdatingBetResults(true);
    toast.info('Fetching bet results from plays888.co History...');
    try {
      // Use the date from currently loaded data (same as Update Scores)
      let dateStr;
      if (data && data.date) {
        dateStr = data.date;
      } else {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        dateStr = yesterday.toISOString().split('T')[0];
      }
      
      const endpoint = `/bets/${league.toLowerCase()}/update-results?date=${dateStr}`;
      
      const response = await axios.post(`${API}${endpoint}`, {}, { timeout: 120000 });
      
      if (response.data.success) {
        toast.success(`Updated ${response.data.bets_matched || response.data.games_updated || 0} bets for ${dateStr}. Record: ${response.data.wins || 0}W-${response.data.losses || 0}L`);
        // Reload data to show updated bet results
        await loadOpportunities();
        
        // For NHL, also reload 1st Period bets to show updated results
        if (league === 'NHL') {
          try {
            const fpResponse = await axios.get(`${API}/nhl/first-period-bets`);
            if (fpResponse.data) {
              setFirstPeriodBets(fpResponse.data);
            }
          } catch (fpError) {
            console.error('Error reloading 1st Period bets:', fpError);
          }
        }
      } else {
        toast.error('Failed to update bet results');
      }
    } catch (error) {
      console.error('Error updating bet results:', error);
      toast.error('Failed to update bet results from plays888');
    } finally {
      setUpdatingBetResults(false);
    }
  };

  const handleUpdateRecords = async () => {
    setUpdatingRecords(true);
    toast.info('Recalculating all records from 12/22/25...');
    try {
      const response = await axios.post(`${API}/process/update-records?start_date=2025-12-22`, {}, { timeout: 60000 });
      
      if (response.data.status === 'success') {
        const records = response.data.records;
        const leagueData = records[league];
        
        // Update the displayed records
        setBettingRecord({ hits: leagueData.betting.wins, misses: leagueData.betting.losses });
        setEdgeRecord({ hits: leagueData.edge.hits, misses: leagueData.edge.misses });
        
        toast.success(`Records updated! Betting: ${leagueData.betting.wins}-${leagueData.betting.losses}, Edge: ${leagueData.edge.hits}-${leagueData.edge.misses}`);
      } else {
        toast.error('Failed to update records');
      }
    } catch (error) {
      console.error('Error updating records:', error);
      toast.error('Failed to update records');
    } finally {
      setUpdatingRecords(false);
    }
  };

  // Edit NHL Line function
  const handleSaveLine = async (gameIndex, newLine) => {
    if (!data.date || !data.games[gameIndex]) return;
    
    setSavingLine(true);
    try {
      const game = data.games[gameIndex];
      const response = await axios.post(`${API}/games/update-line`, {
        league: league.toLowerCase(),
        date: data.date,
        away_team: game.away_team,
        home_team: game.home_team,
        new_line: parseFloat(newLine)
      });
      
      if (response.data.success) {
        // Update local state - update ALL line fields and recalculate edge
        const updatedGames = [...data.games];
        const combinedPpg = game.combined_ppg;
        const newEdge = combinedPpg ? Math.round((combinedPpg - parseFloat(newLine)) * 10) / 10 : game.edge;
        
        // Determine new recommendation based on edge and league thresholds
        let newRecommendation = null;
        if (league === 'NHL' && newEdge !== null) {
          if (newEdge >= 0.6) newRecommendation = 'OVER';
          else if (newEdge <= -0.6) newRecommendation = 'UNDER';
        } else if (league === 'NBA' && newEdge !== null) {
          if (newEdge >= 8) newRecommendation = 'OVER';
          else if (newEdge <= -8) newRecommendation = 'UNDER';
        } else if (league === 'NCAAB' && newEdge !== null) {
          if (newEdge >= 9) newRecommendation = 'OVER';
          else if (newEdge <= -9) newRecommendation = 'UNDER';
        } else if (league === 'NFL' && newEdge !== null) {
          if (newEdge >= 6) newRecommendation = 'OVER';
          else if (newEdge <= -6) newRecommendation = 'UNDER';
        }
        
        updatedGames[gameIndex] = {
          ...updatedGames[gameIndex],
          total: parseFloat(newLine),
          opening_line: parseFloat(newLine),
          live_line: parseFloat(newLine),
          edge: newEdge,
          recommendation: newRecommendation
        };
        setData({ ...data, games: updatedGames });
        toast.success(`Line updated to ${newLine}${newEdge !== game.edge ? `, Edge: ${newEdge}` : ''}`);
        setEditingLine(null);
      } else {
        toast.error('Failed to update line');
      }
    } catch (error) {
      console.error('Error updating line:', error);
      toast.error('Failed to update line');
    } finally {
      setSavingLine(false);
    }
  };

  // Scrape Tomorrow's Opening Lines (8pm Job)
  const [scrapingOpeners, setScrapingOpeners] = useState(false);
  const [scrapingToday, setScrapingToday] = useState(false);
  
  const handleScrapeOpeners = async () => {
    setScrapingOpeners(true);
    toast.info('Scraping tomorrow\'s opening lines...');
    try {
      // Get tomorrow's date in Arizona timezone (UTC-7, no DST)
      const now = new Date();
      // Get Arizona time by subtracting 7 hours from UTC
      const arizonaOffset = -7 * 60; // -7 hours in minutes
      const arizonaTime = new Date(now.getTime() + (arizonaOffset - now.getTimezoneOffset()) * 60000);
      arizonaTime.setDate(arizonaTime.getDate() + 1);
      const targetDate = arizonaTime.toISOString().split('T')[0];
      
      const response = await axios.post(`${API}/process/scrape-openers?target_date=${targetDate}`, {}, { timeout: 180000 });
      
      if (response.data.status === 'success' || response.data.status === 'partial') {
        const leagues = response.data.leagues;
        const summary = Object.entries(leagues)
          .map(([l, d]) => `${l}: ${d.games_stored} games`)
          .join(', ');
        toast.success(`Opening lines scraped! ${summary}`);
        
        // If viewing tomorrow, refresh the data
        if (day === 'tomorrow') {
          loadOpportunities();
        }
      } else {
        toast.error('Failed to scrape opening lines');
      }
    } catch (error) {
      console.error('Error scraping openers:', error);
      toast.error('Failed to scrape opening lines');
    } finally {
      setScrapingOpeners(false);
    }
  };

  // Scrape Today's Games (same as tomorrow but for today)
  const handleScrapeToday = async () => {
    setScrapingToday(true);
    toast.info('Scraping today\'s games and lines...');
    try {
      // Get today's date in Arizona timezone (UTC-7, no DST)
      const now = new Date();
      const arizonaOffset = -7 * 60;
      const arizonaTime = new Date(now.getTime() + (arizonaOffset - now.getTimezoneOffset()) * 60000);
      const targetDate = arizonaTime.toISOString().split('T')[0];
      
      const response = await axios.post(`${API}/process/scrape-openers?target_date=${targetDate}`, {}, { timeout: 180000 });
      
      if (response.data.status === 'success' || response.data.status === 'partial') {
        const leagues = response.data.leagues;
        const summary = Object.entries(leagues)
          .map(([l, d]) => `${l}: ${d.games_stored} games`)
          .join(', ');
        toast.success(`Today's games scraped! ${summary}`);
        
        // Refresh the data if viewing today
        if (day === 'today') {
          loadOpportunities();
        }
      } else {
        toast.error('Failed to scrape today\'s games');
      }
    } catch (error) {
      console.error('Error scraping today:', error);
      toast.error('Failed to scrape today\'s games');
    } finally {
      setScrapingToday(false);
    }
  };

  // Upload PPG Excel file (Process #2)
  const [uploadingPPG, setUploadingPPG] = useState(false);
  const fileInputRef = useRef(null);
  
  const handlePPGExcelUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    setUploadingPPG(true);
    toast.info('Uploading PPG Excel file...');
    
    try {
      // First upload the file to /tmp/PPG.xlsx on the server
      const formData = new FormData();
      formData.append('file', file);
      
      await axios.post(`${API}/ppg/upload-file`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000
      });
      
      // Use 'today' or 'tomorrow' keyword - let backend determine the actual date in Arizona timezone
      const targetDay = day === 'tomorrow' ? 'tomorrow' : 'today';
      
      // Process all 3 leagues
      toast.info(`Processing PPG for all leagues (${targetDay})...`);
      
      const results = [];
      for (const lg of ['NBA', 'NHL', 'NCAAB']) {
        try {
          const response = await axios.post(
            `${API}/ppg/upload-excel?league=${lg}&target_day=${targetDay}`,
            {},
            { timeout: 60000 }
          );
          if (response.data.success) {
            results.push(`${lg}: ${response.data.games_with_ppg}/${response.data.games_count}`);
          }
        } catch (err) {
          results.push(`${lg}: Error`);
        }
      }
      
      toast.success(`PPG Updated! ${results.join(', ')}`);
      
      // Refresh data
      loadOpportunities();
    } catch (error) {
      console.error('Error uploading PPG:', error);
      toast.error('Failed to upload PPG Excel');
    } finally {
      setUploadingPPG(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Export to Excel - using fetch and blob for reliable download
  const handleExport = async () => {
    setExporting(true);
    
    try {
      const downloadUrl = `${BACKEND_URL}/api/export/excel?league=${league}&start_date=2025-12-22`;
      
      // Fetch the file as a blob
      const response = await fetch(downloadUrl);
      if (!response.ok) {
        throw new Error('Export failed');
      }
      
      // Get the blob data
      const blob = await response.blob();
      
      // Create a blob URL and trigger download
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = `${league}_Analysis.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      // Clean up the blob URL
      window.URL.revokeObjectURL(blobUrl);
      
      toast.success(`${league} analysis downloaded!`);
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Failed to export. Please try again.');
    } finally {
      setTimeout(() => setExporting(false), 2000);
    }
  };

  // Handle Ranking PPG selection (High/Low)
  const handleRankingPPGSelect = async (gameNum, rankingType) => {
    try {
      const response = await axios.post(`${API}/opportunities/ranking-ppg`, {
        league: league,
        date: data.date,
        game_num: gameNum,
        ranking_type: rankingType
      });
      
      if (response.data.success) {
        toast.success(`Marked as ${rankingType.toUpperCase()} ranking game`);
        // Update local state to reflect the change
        setData(prev => ({
          ...prev,
          games: prev.games.map(g => 
            g.game_num === gameNum ? { ...g, ranking_ppg: rankingType } : g
          )
        }));
      }
    } catch (error) {
      console.error('Error setting ranking PPG:', error);
      toast.error('Failed to set ranking PPG');
    }
  };

  // Handle clearing ranking PPG selection
  const handleClearRankingPPG = async (gameNum) => {
    try {
      const response = await axios.delete(`${API}/opportunities/ranking-ppg?league=${league}&date=${data.date}&game_num=${gameNum}`);
      
      if (response.data.success) {
        toast.success('Ranking PPG cleared');
        // Update local state to reflect the change
        setData(prev => ({
          ...prev,
          games: prev.games.map(g => 
            g.game_num === gameNum ? { ...g, ranking_ppg: null } : g
          )
        }));
      }
    } catch (error) {
      console.error('Error clearing ranking PPG:', error);
      toast.error('Failed to clear ranking PPG');
    }
  };

  // Handle bet cancellation
  const handleCancelBet = async (gameNum, cancel = true) => {
    try {
      const response = await axios.post(`${API}/opportunities/bet-cancelled`, {
        league: league,
        date: data.date,
        game_num: gameNum,
        cancelled: cancel
      });
      
      if (response.data.success) {
        toast.success(cancel ? 'Bet cancelled' : 'Bet restored');
        // Update local state to reflect the change
        setData(prev => ({
          ...prev,
          games: prev.games.map(g => 
            g.game_num === gameNum ? { 
              ...g, 
              bet_cancelled: cancel,
              has_bet: cancel ? false : g.has_bet,
              user_bet: cancel ? false : g.user_bet,
              bet_type: cancel ? null : g.bet_type,
              bet_line: cancel ? null : g.bet_line
            } : g
          )
        }));
      }
    } catch (error) {
      console.error('Error cancelling bet:', error);
      toast.error('Failed to cancel bet');
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
  // Edge styling: Green if edge meets threshold (positive OR negative)
  // NBA: Green if |edge| >= 8
  // NHL: Green if |edge| >= 0.6
  // NCAAB: Green if |edge| >= 10
  // A negative edge like -16.4 is a strong UNDER play, so it should be green
  const getEdgeStyle = (edge, currentLeague = league) => {
    const absEdge = Math.abs(edge);
    if (currentLeague === 'NBA') {
      if (absEdge >= 8) return 'text-green-400 font-bold';
      return 'text-red-400 font-bold';
    } else if (currentLeague === 'NCAAB') {
      if (absEdge >= 10) return 'text-green-400 font-bold';
      return 'text-red-400 font-bold';
    } else if (currentLeague === 'NFL') {
      if (absEdge >= 6) return 'text-green-400 font-bold';
      return 'text-red-400 font-bold';
    } else {
      // NHL
      if (absEdge >= 0.6) return 'text-green-400 font-bold';
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
      edgeThreshold: 8
    },
    NHL: {
      statLabel: 'GPG',
      combinedLabel: 'GPG Avg',
      overRange: '1-13.5',
      noEdgeRange: '14-18',
      underRange: '18.5-32',
      totalTeams: 32,
      edgeThreshold: 0.6
    },
    NCAAB: {
      statLabel: 'PPG',
      combinedLabel: 'PPG Avg',
      overRange: '1-91',
      noEdgeRange: '92-273',
      underRange: '274-365',
      totalTeams: 365,
      edgeThreshold: 10
    },
    NFL: {
      statLabel: 'PPG',
      combinedLabel: 'PPG Avg',
      overRange: '1-12',
      noEdgeRange: '13-20',
      underRange: '21-32',
      totalTeams: 32,
      edgeThreshold: 6
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
        
        {/* Row 1: Records and Live Lines toggle */}
        <div className="flex flex-wrap items-center gap-4">
          {/* Edge Record Badge */}
          <div className="bg-gradient-to-r from-green-600/20 to-red-600/20 border border-primary/30 rounded-lg px-4 py-2">
            <div className="text-xs text-muted-foreground text-center">Edge Record</div>
            <div className="text-xl font-bold text-center">
              <span className="text-green-400">{edgeRecord.hits}</span>
              <span className="text-muted-foreground mx-1">-</span>
              <span className="text-red-400">{edgeRecord.misses}</span>
            </div>
            <div className="text-[10px] text-muted-foreground text-center">Since 12/22</div>
            <div className="text-[10px] text-center mt-1 border-t border-primary/20 pt-1">
              <span className="text-blue-400">O:</span>
              <span className="text-green-400">{edgeRecord.over.split('-')[0]}</span>
              <span className="text-muted-foreground">-</span>
              <span className="text-red-400">{edgeRecord.over.split('-')[1]}</span>
              <span className="text-muted-foreground mx-1">|</span>
              <span className="text-blue-400">U:</span>
              <span className="text-green-400">{edgeRecord.under.split('-')[0]}</span>
              <span className="text-muted-foreground">-</span>
              <span className="text-red-400">{edgeRecord.under.split('-')[1]}</span>
            </div>
          </div>
          {/* Betting Record Badge */}
          <div className="bg-gradient-to-r from-yellow-600/20 to-orange-600/20 border border-yellow-500/30 rounded-lg px-4 py-2">
            <div className="text-xs text-muted-foreground text-center">💰 Betting Record</div>
            <div className="text-xl font-bold text-center">
              <span className="text-green-400">{bettingRecord.hits}</span>
              <span className="text-muted-foreground mx-1">-</span>
              <span className="text-red-400">{bettingRecord.misses}</span>
            </div>
            <div className="text-[10px] text-muted-foreground text-center">Since 12/22</div>
          </div>
          {/* Ranking PPG Record Badge */}
          <div className="bg-gradient-to-r from-emerald-600/20 to-rose-600/20 border border-emerald-500/30 rounded-lg px-4 py-2">
            <div className="text-xs text-muted-foreground text-center">📊 Ranking PPG</div>
            <div className="text-sm font-bold text-center flex flex-col gap-0.5">
              <div>
                <span className="text-green-400 text-xs">H:</span>
                <span className="text-green-400 ml-1">{rankingPPGRecord.high.hits}</span>
                <span className="text-muted-foreground mx-0.5">-</span>
                <span className="text-red-400">{rankingPPGRecord.high.misses}</span>
              </div>
              <div>
                <span className="text-red-400 text-xs">L:</span>
                <span className="text-green-400 ml-1">{rankingPPGRecord.low.hits}</span>
                <span className="text-muted-foreground mx-0.5">-</span>
                <span className="text-red-400">{rankingPPGRecord.low.misses}</span>
              </div>
            </div>
          </div>
          {/* Public Consensus Record Badge - Click to open compound breakdown */}
          <div 
            className="bg-gradient-to-r from-cyan-600/20 to-blue-600/20 border border-cyan-500/30 rounded-lg px-4 py-2 cursor-pointer hover:border-cyan-400/50 transition-all"
            onClick={() => setShowCompoundModal(true)}
            title="Click to view Fade The Public breakdown"
          >
            <div className="flex items-center justify-center gap-2">
              <span className="text-xs text-muted-foreground">📢 Public</span>
              <span className="text-[10px] bg-cyan-600/30 text-cyan-300 px-1.5 py-0.5 rounded">Breakdown</span>
            </div>
            <div className="text-xl font-bold text-center">
              {loadingPublicRecord ? (
                <span className="text-muted-foreground">...</span>
              ) : (
                <>
                  <span className="text-green-400">{publicRecord.hits}</span>
                  <span className="text-muted-foreground mx-1">-</span>
                  <span className="text-red-400">{publicRecord.misses}</span>
                </>
              )}
            </div>
            {publicRecord.winPct !== undefined && !loadingPublicRecord && (
              <div className={`text-[10px] text-center font-medium ${publicRecord.winPct >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                {publicRecord.winPct}% Win Rate
              </div>
            )}
          </div>
          {/* NHL 1st Period Badge - Only show for NHL - Click to open breakdown */}
          {league === 'NHL' && (
            <div 
              className="bg-gradient-to-r from-green-600/20 to-emerald-600/20 border border-green-500/30 rounded-lg px-4 py-2 cursor-pointer hover:border-green-400/50 transition-all"
              onClick={() => setShowFirstPeriodModal(true)}
              title="Click to view 1st Period goals breakdown"
            >
              <div className="flex items-center justify-center gap-2">
                <span className="text-xs text-muted-foreground">🏒 1st Period Stats</span>
                <span className="text-[10px] bg-green-600/30 text-green-300 px-1.5 py-0.5 rounded">Breakdown</span>
              </div>
              <div className="text-xl font-bold text-center text-green-400">
                0-3 | {firstPeriodStats.pct03}%
              </div>
              <div className="text-[10px] text-muted-foreground text-center">Games 0-3 Goals</div>
              <div className="text-[10px] text-center mt-1 border-t border-green-500/20 pt-1">
                <span className="text-gray-400">L3:</span>
                <span className="text-green-400 ml-1">{firstPeriodStats.l3Pct}%</span>
                <span className="text-muted-foreground mx-1">|</span>
                <span className="text-gray-400">L5:</span>
                <span className="text-green-400 ml-1">{firstPeriodStats.l5Pct}%</span>
              </div>
            </div>
          )}
          {/* NHL 1st Period Bets Badge - Only show for NHL */}
          {league === 'NHL' && (
            <div 
              className="bg-gradient-to-r from-purple-600/20 to-blue-600/20 border border-purple-500/30 rounded-lg px-4 py-2 cursor-pointer hover:border-purple-400/50 transition-all"
              onClick={() => setShowFirstPeriodBetsModal(true)}
              title="Click to view 1st Period betting record"
            >
              <div className="flex items-center justify-center gap-2">
                <span className="text-xs text-muted-foreground">💰 1st Period Bets</span>
                <span className="text-[10px] bg-purple-600/30 text-purple-300 px-1.5 py-0.5 rounded">Record</span>
              </div>
              <div className="text-xl font-bold text-center">
                <span className="text-green-400">{firstPeriodBets.summary?.total?.wins || 0}</span>
                <span className="text-gray-500 mx-1">-</span>
                <span className="text-red-400">{firstPeriodBets.summary?.total?.losses || 0}</span>
              </div>
              <div className="text-[10px] text-muted-foreground text-center">
                {firstPeriodBets.summary?.total?.wins + firstPeriodBets.summary?.total?.losses > 0 
                  ? `${((firstPeriodBets.summary?.total?.wins / (firstPeriodBets.summary?.total?.wins + firstPeriodBets.summary?.total?.losses)) * 100).toFixed(1)}% Win`
                  : 'No bets'}
              </div>
              <div className={`text-[10px] text-center mt-1 border-t border-purple-500/20 pt-1 font-bold ${(firstPeriodBets.summary?.total?.profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {(firstPeriodBets.summary?.total?.profit || 0) >= 0 ? '+' : ''}${(firstPeriodBets.summary?.total?.profit || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
              </div>
            </div>
          )}
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
        </div>
        
        {/* Row 2: Action Buttons */}
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <Button 
            onClick={handleRefresh} 
            disabled={refreshing}
            className="flex items-center gap-2"
            data-testid="refresh-lines-bets-btn"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh Lines & Bets
          </Button>
          <Button 
            onClick={handleUpdateScores} 
            disabled={updatingScores}
            variant="secondary"
            size="sm"
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white"
          >
            <TrendingUp className={`w-4 h-4 ${updatingScores ? 'animate-pulse' : ''}`} />
            {updatingScores ? 'Updating...' : 'Update Scores'}
          </Button>
          <Button 
            onClick={handleUpdateBetResults} 
            disabled={updatingBetResults}
            variant="secondary"
            size="sm"
            className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white"
          >
            <span className={updatingBetResults ? 'animate-pulse' : ''}>💰</span>
            {updatingBetResults ? 'Updating...' : 'Update Bet Results'}
          </Button>
          <Button 
            onClick={handleUpdateRecords} 
            disabled={updatingRecords}
            variant="outline"
            size="sm"
            className="flex items-center gap-2 border-orange-500/50 text-orange-400 hover:bg-orange-500/10"
          >
            <span className={updatingRecords ? 'animate-spin' : ''}>📊</span>
            {updatingRecords ? 'Updating...' : 'Update Records'}
          </Button>
          <Button 
            onClick={handleScrapeOpeners} 
            disabled={scrapingOpeners}
            variant="outline"
            size="sm"
            className="flex items-center gap-2 border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10"
          >
            <Calendar className={`w-4 h-4 ${scrapingOpeners ? 'animate-pulse' : ''}`} />
            {scrapingOpeners ? 'Scraping...' : 'Scrape Tomorrow'}
          </Button>
          <Button 
            onClick={handleScrapeToday} 
            disabled={scrapingToday}
            variant="outline"
            size="sm"
            className="flex items-center gap-2 border-purple-500/50 text-purple-400 hover:bg-purple-500/10"
            data-testid="scrape-today-btn"
          >
            <Calendar className={`w-4 h-4 ${scrapingToday ? 'animate-pulse' : ''}`} />
            {scrapingToday ? 'Scraping...' : 'Scrape Today'}
          </Button>
          <Button 
            onClick={handleExport} 
            disabled={exporting}
            variant="outline"
            size="sm"
            className="flex items-center gap-2"
          >
            <Download className={`w-4 h-4 ${exporting ? 'animate-pulse' : ''}`} />
            {exporting ? 'Exporting...' : 'Export Excel'}
          </Button>
          {league === 'NCAAB' && (day === 'tomorrow' || day === 'today') && (
            <Button 
              onClick={handleNCAABPPGUpdate} 
              disabled={updatingPPG}
              variant="secondary"
              size="sm"
              className="flex items-center gap-2 bg-yellow-600 hover:bg-yellow-700 text-white"
            >
              <Target className={`w-4 h-4 ${updatingPPG ? 'animate-pulse' : ''}`} />
              {updatingPPG ? 'Updating PPG...' : 'Update PPG (L3)'}
            </Button>
          )}
          {(day === 'tomorrow' || day === 'today') && (
            <>
              <input
                type="file"
                ref={fileInputRef}
                accept=".xlsx,.xls"
                onChange={handlePPGExcelUpload}
                className="hidden"
                data-testid="ppg-file-input"
              />
              <Button 
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingPPG}
                variant="outline"
                size="sm"
                className="flex items-center gap-2 border-green-500/50 text-green-400 hover:bg-green-500/10"
                data-testid="upload-ppg-btn"
              >
                <Upload className={`w-4 h-4 ${uploadingPPG ? 'animate-pulse' : ''}`} />
                {uploadingPPG ? 'Uploading...' : 'Upload PPG Excel'}
              </Button>
            </>
          )}
        </div>
      </div>

      {/* League Tabs - NFL eliminated */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex gap-2">
          {['NBA', 'NHL', 'NCAAB', 'NFL'].map((l) => (
            <button
              key={l}
              onClick={() => setLeague(l)}
              className={`px-4 py-2 rounded-lg font-bold text-sm transition-all ${
                league === l
                  ? 'bg-primary text-primary-foreground shadow-lg'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
            >
              {l === 'NBA' ? '🏀' : l === 'NHL' ? '🏒' : l === 'NFL' ? '🏈' : '🎓'} {l}
            </button>
          ))}
        </div>
        
        <div className="h-6 w-px bg-border hidden sm:block" />
        
        {/* Day Tabs - Different for NFL (week selector) vs other leagues */}
        <div className="flex gap-2 items-center">
          {league === 'NFL' ? (
            /* NFL Week Selector */
            <div className="relative">
              <button
                onClick={() => setShowWeekPicker(!showWeekPicker)}
                className="px-4 py-2 rounded-lg font-medium text-sm transition-all flex items-center gap-2 bg-orange-600 text-white shadow-lg hover:bg-orange-700"
              >
                <Calendar className="w-4 h-4" />
                {selectedNflWeek ? `Week ${selectedNflWeek}` : 'Select Week'}
              </button>
              {showWeekPicker && (
                <div className="absolute top-full left-0 mt-2 z-50 bg-card border border-border rounded-lg shadow-xl p-2 min-w-[280px] max-h-[400px] overflow-auto">
                  <div className="text-sm text-muted-foreground mb-2 px-2 font-medium">Select NFL Week:</div>
                  <div className="grid grid-cols-3 gap-1">
                    {nflWeeks.map((weekInfo) => (
                      <button
                        key={weekInfo.week}
                        onClick={() => handleNflWeekSelect(weekInfo.week)}
                        className={`px-3 py-2 rounded text-sm transition-all ${
                          selectedNflWeek === weekInfo.week
                            ? 'bg-orange-600 text-white'
                            : 'bg-muted hover:bg-muted/80 text-foreground'
                        }`}
                        title={`${weekInfo.game_count} games | ${weekInfo.date_range}`}
                      >
                        Wk {weekInfo.week}
                      </button>
                    ))}
                  </div>
                  <div className="text-xs text-muted-foreground mt-2 px-2 border-t border-border pt-2">
                    {selectedNflWeek && nflWeeks.find(w => w.week === selectedNflWeek) && (
                      <>
                        <div>📅 {nflWeeks.find(w => w.week === selectedNflWeek).date_range}</div>
                        <div>🏈 {nflWeeks.find(w => w.week === selectedNflWeek).game_count} games</div>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Calendar Button for other leagues */
            <>
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
              
              {/* Day selector for non-NFL leagues */}
              {['yesterday', 'today', 'tomorrow'].map((d) => (
                <button
                  key={d}
                  onClick={() => { setDay(d); setCustomDate(''); }}
                  className={`px-4 py-2 rounded-lg font-medium text-sm transition-all ${
                    day === d
                      ? d === 'yesterday' ? 'bg-purple-600 text-white shadow-lg' : 
                        d === 'today' ? 'bg-blue-600 text-white shadow-lg' : 'bg-green-600 text-white shadow-lg'
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
            {league === 'NFL' && selectedNflWeek ? (
              <>
                <div><span className="text-muted-foreground">Week:</span> <span className="font-mono text-orange-400">Week {selectedNflWeek}</span></div>
                <div><span className="text-muted-foreground">Dates:</span> <span className="font-mono">{data.date_range || data.date || 'N/A'}</span></div>
              </>
            ) : (
              <div><span className="text-muted-foreground">Date:</span> <span className="font-mono">{data.date || 'N/A'}</span></div>
            )}
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
                  const edgeThreshold = league === 'NBA' ? 8 : league === 'NCAAB' ? 10 : league === 'NFL' ? 6 : 0.6;
                  return g.result_hit === true && g.edge !== null && g.edge !== undefined && Math.abs(g.edge) >= edgeThreshold;
                }).length}</span></div>
                <div><span className="text-muted-foreground">Misses:</span> <span className="font-mono text-red-400">{data.games.filter(g => {
                  const edgeThreshold = league === 'NBA' ? 8 : league === 'NCAAB' ? 10 : league === 'NFL' ? 6 : 0.6;
                  return g.result_hit === false && g.edge !== null && g.edge !== undefined && Math.abs(g.edge) >= edgeThreshold;
                }).length}</span></div>
                <div className="border-l border-border pl-4 ml-2">
                  <span className="text-muted-foreground">💰 My Bets:</span>{' '}
                  {data.actual_bet_record ? (
                    <>
                      <span className="font-mono text-green-400">{data.actual_bet_record.wins}</span>
                      <span className="text-muted-foreground">-</span>
                      <span className="font-mono text-red-400">{data.actual_bet_record.losses}</span>
                    </>
                  ) : (
                    <>
                      <span className="font-mono text-green-400">{data.games.filter(g => g.user_bet && g.user_bet_hit === true).length}</span>
                      <span className="text-muted-foreground">-</span>
                      <span className="font-mono text-red-400">{data.games.filter(g => g.user_bet && g.user_bet_hit === false).length}</span>
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Today's Plays - only show games with active bets */}
      {/* Games Table */}
      <Card className="glass-card neon-border">
        <CardHeader className="border-b border-border pb-4">
          <CardTitle className="text-lg">
            {league} Games Analysis - {
              day === 'custom' && customDate ? customDate : day === 'yesterday' ? 'Yesterday (Results)' : day === 'tomorrow' ? 'Tomorrow' : 'Today'
            }
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4 overflow-x-auto">
          {(() => {
            // Determine if we're viewing historical data (past dates with results)
            // For NFL, when viewing by week, it's always historical data
            const isHistorical = day === 'yesterday' || day === 'custom' || (league === 'NFL' && selectedNflWeek);
            // Show historical columns if viewing past data OR if any game has final scores
            const hasAnyFinalScores = data.games && data.games.some(g => g.final_score || (g.away_score !== undefined && g.home_score !== undefined));
            const showHistoricalColumns = isHistorical || hasAnyFinalScores;
            
            return data.games && data.games.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-2">#</th>
                  <th className="text-left py-3 px-2">Time</th>
                  <th className="text-center py-3 px-1" title="Ranking PPG Selection">Rank</th>
                  <th className="text-left py-3 px-2">Away</th>
                  <th className="text-center py-3 px-1"></th>
                  <th className="text-left py-3 px-2">Home</th>
                  {showHistoricalColumns && <th className="text-center py-3 px-2" title="Public Consensus Pick">Public</th>}
                  <th className="text-center py-3 px-2">Open</th>
                  <th className="text-center py-3 px-2">Line</th>
                  {showHistoricalColumns && <th className="text-center py-3 px-2">Final</th>}
                  <th className="text-center py-3 px-2">{league === 'NBA' || league === 'NCAAB' || league === 'NFL' ? 'PPG' : 'GPG'} Avg</th>
                  <th className="text-center py-3 px-2">Edge</th>
                  {!showHistoricalColumns && <th className="text-center py-3 px-2" title="Opening spread/moneyline from Scrape Tomorrow">{league === 'NHL' ? 'Open ML' : 'Open Sprd'}</th>}
                  {!showHistoricalColumns && <th className="text-center py-3 px-2" title="Live spread/moneyline from Refresh Lines">{league === 'NHL' ? 'ML' : 'Sprd'}</th>}
                  <th className="text-center py-3 px-2">{showHistoricalColumns ? 'Result' : 'Bet'}</th>
                </tr>
              </thead>
              <tbody>
                {data.games.map((game, index) => {
                  // Check if edge is below threshold - if so, it's a "No Bet" game
                  const edgeThreshold = league === 'NBA' ? 8 : league === 'NCAAB' ? 10 : league === 'NFL' ? 6 : 0.6;
                  const isNoBet = game.edge === null || game.edge === undefined || Math.abs(game.edge) < edgeThreshold;
                  
                  // Calculate dot-based recommendation
                  const awaySeasonRank = game.away_ppg_rank || game.away_gpg_rank || 15;
                  const awayLast3Rank = game.away_last3_rank || 15;
                  const homeSeasonRank = game.home_ppg_rank || game.home_gpg_rank || 15;
                  const homeLast3Rank = game.home_last3_rank || 15;
                  
                  // Helper function to get dot color based on league and rank
                  // NBA/NHL: 30-32 teams split into 4 groups of 8
                  // NCAAB: 365 teams - Green(1-92), Blue(93-184), Yellow(185-276), Red(277-365), White(unknown/null)
                  const getDotColor = (rank) => {
                    if (rank === null || rank === undefined) return 'bg-white/50 border border-gray-400'; // Unknown
                    if (league === 'NCAAB') {
                      if (rank <= 92) return 'bg-green-500';
                      if (rank <= 184) return 'bg-blue-500';
                      if (rank <= 276) return 'bg-yellow-500';
                      if (rank <= 365) return 'bg-red-500';
                      return 'bg-white/50 border border-gray-400'; // Unknown (rank > 365)
                    } else {
                      // NBA, NHL - 30-32 teams
                      if (rank <= 8) return 'bg-green-500';
                      if (rank <= 16) return 'bg-blue-500';
                      if (rank <= 24) return 'bg-yellow-500';
                      return 'bg-red-500';
                    }
                  };
                  
                  // Count dots by color using league-specific thresholds
                  const ranks = [awaySeasonRank, awayLast3Rank, homeSeasonRank, homeLast3Rank];
                  let greens, blues, yellows, reds;
                  if (league === 'NCAAB') {
                    greens = ranks.filter(r => r !== null && r <= 92).length;
                    blues = ranks.filter(r => r !== null && r > 92 && r <= 184).length;
                    yellows = ranks.filter(r => r !== null && r > 184 && r <= 276).length;
                    reds = ranks.filter(r => r !== null && r > 276 && r <= 365).length;
                  } else {
                    greens = ranks.filter(r => r <= 8).length;
                    blues = ranks.filter(r => r > 8 && r <= 16).length;
                    yellows = ranks.filter(r => r > 16 && r <= 24).length;
                    reds = ranks.filter(r => r > 24).length;
                  }
                  
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
                    // For today/tomorrow - highlight ALL games that meet edge threshold
                    // Edge threshold: NBA >= 8, NHL >= 0.6, NCAAB >= 10
                    if (isNoBet) {
                      rowStyle = '';  // Below threshold - no highlight
                    } else {
                      // Above threshold - ALWAYS highlight based on recommendation
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

                  // Determine if this is a spread bet for special styling
                  const isSpreadBet = game.is_spread_bet || game.bet_type === 'SPREAD';

                  return (
                    <tr 
                      key={game.game_num}
                      className={`border-b border-border/50 ${rowStyle} ${game.has_bet && !game.bet_cancelled ? 'ring-2 ring-yellow-500 bg-yellow-500/10' : ''} ${game.user_bet && isSpreadBet ? 'ring-2 ring-purple-500 bg-purple-500/10' : ''} ${game.bet_cancelled ? 'opacity-60' : ''}`}
                    >
                      <td className="py-3 px-2 font-mono text-muted-foreground">
                        {game.bet_cancelled ? (
                          <button
                            onClick={() => handleCancelBet(game.game_num, false)}
                            className="mr-1 text-gray-500 hover:text-yellow-500 transition-colors"
                            title="Bet cancelled - click to restore"
                          >
                            🚫
                          </button>
                        ) : (game.has_bet || game.user_bet) ? (
                          <span className="inline-flex items-center">
                            <span className={`mr-0.5 ${isSpreadBet ? 'text-purple-400' : ''}`} title={game.has_bet ? `Active bet: ${game.bet_type}${game.bet_count > 1 ? ` (x${game.bet_count})` : ''}` : isSpreadBet ? 'Spread bet on this game' : 'You bet on this game'}>
                              {isSpreadBet ? '🎰' : '💰'}{game.bet_count > 1 && <span className={`text-xs font-bold ${isSpreadBet ? 'text-purple-400' : 'text-yellow-400'}`}>x{game.bet_count}</span>}
                            </span>
                            <button
                              onClick={() => handleCancelBet(game.game_num, true)}
                              className="text-[10px] text-gray-500 hover:text-red-500 transition-colors ml-0.5"
                              title="Cancel bet (e.g., if you placed both OVER and UNDER)"
                            >
                              ✕
                            </button>
                          </span>
                        ) : null}
                        {index + 1}
                      </td>
                      <td className="py-3 px-2 text-muted-foreground">{game.time}</td>
                      {/* Ranking PPG Selection Buttons */}
                      <td className="py-3 px-1">
                        <div className="flex flex-col gap-0.5">
                          {game.ranking_ppg ? (
                            // Show selected state - click to clear
                            <button
                              onClick={() => handleClearRankingPPG(game.game_num)}
                              className={`px-1.5 py-0.5 text-[10px] font-bold rounded cursor-pointer hover:opacity-70 transition-opacity ${
                                game.ranking_ppg === 'high' 
                                  ? 'bg-green-500 text-white' 
                                  : 'bg-red-500 text-white'
                              }`}
                              title={`${game.ranking_ppg.toUpperCase()} ranking - click to clear`}
                            >
                              {game.ranking_ppg === 'high' ? 'H' : 'L'}
                            </button>
                          ) : (
                            // Show both buttons for selection
                            <>
                              <button
                                onClick={() => handleRankingPPGSelect(game.game_num, 'high')}
                                className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-green-500/20 text-green-400 hover:bg-green-500 hover:text-white transition-all border border-green-500/30"
                                title="Mark as HIGH ranking game (all green dots)"
                              >
                                H
                              </button>
                              <button
                                onClick={() => handleRankingPPGSelect(game.game_num, 'low')}
                                className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-red-500/20 text-red-400 hover:bg-red-500 hover:text-white transition-all border border-red-500/30"
                                title="Mark as LOW ranking game (all red dots)"
                              >
                                L
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                      {/* Away Team with Rankings and Score */}
                      <td className={`py-3 px-2 ${textStyle}`}>
                        <div className="flex flex-col">
                          <div className="flex items-center gap-1">
                            <span className="text-xs font-mono text-blue-400/70">
                              {game.away_ppg_rank || game.away_gpg_rank}/{game.away_last3_rank}
                            </span>
                            {/* Show consensus % next to ranking if away team has higher % - in RED (always show if available) */}
                            {game.away_consensus_pct && game.away_consensus_pct > (game.home_consensus_pct || 0) && (
                              <span className="text-xs font-bold text-red-500">
                                {game.away_consensus_pct}%
                              </span>
                            )}
                          </div>
                          <span className="font-medium">{game.away_team}</span>
                          {/* Show away team score below team name for historical */}
                          {showHistoricalColumns && game.away_score !== undefined && game.away_score !== null && (
                            <span className="text-sm font-bold text-purple-300 bg-purple-500/20 px-1.5 py-0.5 rounded mt-0.5 text-center">
                              {game.away_score}
                            </span>
                          )}
                        </div>
                      </td>
                      {/* Colored Dots - All 4 together in the middle */}
                      <td className="py-3 px-1">
                        <div className="flex items-center justify-center gap-0.5">
                          <span className={`w-2.5 h-2.5 rounded-full ${getDotColor(game.away_ppg_rank || game.away_gpg_rank)}`}></span>
                          <span className={`w-2.5 h-2.5 rounded-full ${getDotColor(game.away_last3_rank)}`}></span>
                          <span className={`w-2.5 h-2.5 rounded-full ${getDotColor(game.home_ppg_rank || game.home_gpg_rank)}`}></span>
                          <span className={`w-2.5 h-2.5 rounded-full ${getDotColor(game.home_last3_rank)}`}></span>
                        </div>
                      </td>
                      {/* Home Team with Rankings and Score */}
                      <td className={`py-3 px-2 ${textStyle}`}>
                        <div className="flex flex-col">
                          <div className="flex items-center gap-1">
                            <span className="text-xs font-mono text-orange-400/70">
                              {game.home_ppg_rank || game.home_gpg_rank}/{game.home_last3_rank}
                            </span>
                            {/* Show consensus % next to ranking if home team has higher % - in RED (always show if available) */}
                            {game.home_consensus_pct && game.home_consensus_pct > (game.away_consensus_pct || 0) && (
                              <span className="text-xs font-bold text-red-500">
                                {game.home_consensus_pct}%
                              </span>
                            )}
                          </div>
                          <span className="font-medium">{game.home_team}</span>
                          {/* Show home team score below team name for historical */}
                          {showHistoricalColumns && game.home_score !== undefined && game.home_score !== null && (
                            <span className="text-sm font-bold text-purple-300 bg-purple-500/20 px-1.5 py-0.5 rounded mt-0.5 text-center">
                              {game.home_score}
                            </span>
                          )}
                        </div>
                      </td>
                      {/* Public Consensus Pick column - shows spread of team with higher consensus % (56%+) and HIT/MISS */}
                      {showHistoricalColumns && (
                        <td className="py-3 px-2 text-center">
                          {(() => {
                            const awayPct = game.away_consensus_pct || 0;
                            const homePct = game.home_consensus_pct || 0;
                            
                            // Determine which team has higher consensus
                            if (awayPct === 0 && homePct === 0) {
                              return <span className="text-muted-foreground">-</span>;
                            }
                            
                            const isAwayPublicPick = awayPct >= homePct;
                            const publicPct = isAwayPublicPick ? awayPct : homePct;
                            
                            // Only show if public pick has 56% or above
                            if (publicPct < 56) {
                              return <span className="text-muted-foreground">-</span>;
                            }
                            
                            // PRIORITY: Covers.com spread first, CBS Sports as fallback
                            // away_spread = Covers.com spread for away team
                            // spread = CBS Sports live spread (home team's perspective)
                            let publicSpread = null;
                            
                            if (isAwayPublicPick) {
                              // Away team is public pick
                              if (game.away_spread !== null && game.away_spread !== undefined) {
                                // Use Covers.com spread directly for away team
                                publicSpread = parseFloat(game.away_spread);
                              } else if (game.spread !== null && game.spread !== undefined) {
                                // Fallback: CBS Sports (invert home spread for away)
                                publicSpread = -parseFloat(game.spread);
                              }
                            } else {
                              // Home team is public pick
                              if (game.away_spread !== null && game.away_spread !== undefined) {
                                // Covers.com: home spread = -away_spread
                                publicSpread = -parseFloat(game.away_spread);
                              } else if (game.spread !== null && game.spread !== undefined) {
                                // Fallback: CBS Sports spread directly for home
                                publicSpread = parseFloat(game.spread);
                              }
                            }
                            
                            // Calculate if the public pick covered the spread
                            let publicPickResult = null;
                            
                            if (game.away_score !== undefined && game.home_score !== undefined && publicSpread !== null) {
                              const awayScore = parseFloat(game.away_score);
                              const homeScore = parseFloat(game.home_score);
                              
                              if (isAwayPublicPick) {
                                const awayCovered = awayScore + publicSpread > homeScore;
                                const push = awayScore + publicSpread === homeScore;
                                publicPickResult = push ? 'PUSH' : (awayCovered ? 'HIT' : 'MISS');
                              } else {
                                const homeCovered = homeScore + publicSpread > awayScore;
                                const push = homeScore + publicSpread === awayScore;
                                publicPickResult = push ? 'PUSH' : (homeCovered ? 'HIT' : 'MISS');
                              }
                            }
                            
                            return (
                              <div className="flex flex-col items-center">
                                <span className="font-mono font-bold">
                                  {publicSpread !== null ? (publicSpread >= 0 ? '+' : '') + publicSpread : '-'}
                                </span>
                                {publicPickResult && (
                                  <span className={`text-xs font-bold ${
                                    publicPickResult === 'HIT' ? 'text-green-400' : 
                                    publicPickResult === 'PUSH' ? 'text-yellow-400' : 'text-red-400'
                                  }`}>
                                    {publicPickResult}
                                  </span>
                                )}
                              </div>
                            );
                          })()}
                        </td>
                      )}
                      {/* Opening Line column - show for ALL views (Today, Tomorrow, Yesterday) */}
                      <td className={`py-3 px-2 text-center font-mono text-muted-foreground`}>
                        {game.opening_line || game.total || '-'}
                      </td>
                      {/* Current/Live Line column - with Edit option for NHL */}
                      <td className={`py-3 px-2 text-center font-mono ${textStyle}`}>
                        {(() => {
                          // For non-historical: show live_line if available, otherwise total/opening_line
                          const currentLine = game.live_line || game.total || game.opening_line;
                          const openingLine = game.opening_line || game.total;
                          const lineMovement = currentLine && openingLine ? currentLine - openingLine : 0;
                          
                          // Check if we're editing this game's line
                          if (editingLine && editingLine.gameIndex === index && league === 'NHL') {
                            return (
                              <div className="flex items-center justify-center gap-1">
                                <input
                                  type="number"
                                  step="0.5"
                                  value={editingLine.value}
                                  onChange={(e) => setEditingLine({ ...editingLine, value: e.target.value })}
                                  className="w-16 px-1 py-0.5 text-center bg-gray-800 border border-gray-600 rounded text-sm"
                                  autoFocus
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') handleSaveLine(index, editingLine.value);
                                    if (e.key === 'Escape') setEditingLine(null);
                                  }}
                                />
                                <button
                                  onClick={() => handleSaveLine(index, editingLine.value)}
                                  disabled={savingLine}
                                  className="p-0.5 text-green-400 hover:text-green-300"
                                  title="Save"
                                >
                                  <Check className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => setEditingLine(null)}
                                  className="p-0.5 text-red-400 hover:text-red-300"
                                  title="Cancel"
                                >
                                  <X className="w-4 h-4" />
                                </button>
                              </div>
                            );
                          }
                          
                          if (!currentLine) return <span className="text-gray-500 text-xs">NO LINE</span>;
                          
                          // Calculate bet line movement (if user bet, compare closing to bet line)
                          const betLineMovement = game.user_bet && game.bet_line ? currentLine - game.bet_line : 0;
                          
                          return (
                            <div className="flex flex-col items-center group relative">
                              {/* Current/closing line with movement indicator from bet line */}
                              <span className={betLineMovement !== 0 ? (betLineMovement > 0 ? 'text-green-400' : 'text-red-400') : (lineMovement !== 0 ? (lineMovement > 0 ? 'text-green-400' : 'text-red-400') : '')}>
                                {currentLine}
                                {/* Arrow for bet line movement (historical) */}
                                {game.user_bet && game.bet_line && betLineMovement !== 0 && (
                                  <span className="text-xs ml-1">
                                    {betLineMovement > 0 ? '↑' : '↓'}
                                  </span>
                                )}
                                {/* Arrow for opening line movement (today/tomorrow) */}
                                {!showHistoricalColumns && !game.user_bet && lineMovement !== 0 && (
                                  <span className="text-xs ml-1">
                                    {lineMovement > 0 ? '↑' : '↓'}
                                  </span>
                                )}
                              </span>
                              {/* Edit button for NHL - shows on hover */}
                              {league === 'NHL' && (
                                <button
                                  onClick={() => setEditingLine({ gameIndex: index, value: currentLine?.toString() || '' })}
                                  className="absolute -right-4 top-1/2 -translate-y-1/2 p-0.5 text-gray-500 hover:text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                  title="Edit line"
                                >
                                  <Pencil className="w-3 h-3" />
                                </button>
                              )}
                              {/* Show bet-time line if user bet on this game */}
                              {game.user_bet && game.bet_line && (
                                <span className={`text-xs font-bold ${isSpreadBet ? 'text-purple-400' : 'text-yellow-400'}`} title={isSpreadBet ? 'Spread when bet was placed' : 'Line when bet was placed'}>
                                  {isSpreadBet ? '📊' : '🎯'} {isSpreadBet && game.bet_line > 0 ? '+' : ''}{game.bet_line}
                                </span>
                              )}
                            </div>
                          );
                        })()}
                      </td>
                      {/* Final Score column - PURPLE HIGHLIGHT - Shows total score only */}
                      {showHistoricalColumns && (
                        <td className={`py-3 px-2 text-center font-mono font-bold bg-purple-500/20 text-purple-300`}>
                          {game.final_score || '-'}
                        </td>
                      )}
                      <td className={`py-3 px-2 text-center font-bold ${textStyle}`}>
                        {/* For NCAAB, only show PPG if BOTH teams have data */}
                        {league === 'NCAAB' ? (
                          (game.away_ppg_value && game.home_ppg_value) 
                            ? game.combined_ppg 
                            : <span className="text-muted-foreground text-xs">-</span>
                        ) : (
                          game.combined_ppg || game.combined_gpg || game.game_avg || '-'
                        )}
                      </td>
                      <td className="py-3 px-2 text-center">
                        {/* For NCAAB, only show edge if both teams have PPG data */}
                        {league === 'NCAAB' && !(game.away_ppg_value && game.home_ppg_value) ? (
                          <span className="text-muted-foreground">-</span>
                        ) : game.edge !== null && game.edge !== undefined ? (
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
                      {/* OPENING Spread (NBA/NCAAB) or Moneyline (NHL) - only for non-historical */}
                      {!showHistoricalColumns && (
                        <td className="py-3 px-2 text-center">
                          {league === 'NHL' ? (
                            // NHL: Show opening moneyline (fallback to moneyline if opening not set)
                            (game.opening_moneyline || game.moneyline) ? (
                              <div className="flex flex-col items-center">
                                <span className="text-xs text-gray-400">{game.opening_moneyline_team || game.moneyline_team || game.home_team}</span>
                                <span className={`font-bold ${(game.opening_moneyline || game.moneyline) < 0 ? 'text-red-400' : 'text-green-400'}`}>
                                  {game.opening_moneyline || game.moneyline}
                                </span>
                              </div>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )
                          ) : (
                            // NBA/NCAAB: Show opening spread (fallback to spread if opening not set)
                            (game.opening_spread || game.spread) ? (
                              <div className="flex flex-col items-center">
                                <span className="text-xs text-gray-400">{game.opening_spread_team || game.spread_team || game.home_team}</span>
                                {(() => {
                                  // Use helper function to determine if spread_team is home or away
                                  const spreadTeam = game.opening_spread_team || game.spread_team;
                                  const spreadValue = game.opening_spread || game.spread;
                                  // If spread_team is NOT the home team, invert the spread
                                  const isHome = isSpreadTeamHome(spreadTeam, game.home_team, game.away_team);
                                  const displaySpread = isHome ? spreadValue : -spreadValue;
                                  return (
                                    <span className={`font-bold ${displaySpread < 0 ? 'text-red-400' : 'text-green-400'}`}>
                                      {displaySpread > 0 ? '+' : ''}{displaySpread}
                                    </span>
                                  );
                                })()}
                              </div>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )
                          )}
                        </td>
                      )}
                      {/* LIVE Spread (NBA/NCAAB) or Moneyline (NHL) - only for non-historical */}
                      {!showHistoricalColumns && (
                        <td className="py-3 px-2 text-center">
                          {league === 'NHL' ? (
                            // NHL: Show live moneyline
                            game.moneyline ? (
                              <div className="flex flex-col items-center">
                                <span className="text-xs text-gray-400">{game.moneyline_team || game.home_team}</span>
                                <span className={`font-bold ${game.moneyline < 0 ? 'text-red-400' : 'text-green-400'}`}>
                                  {game.moneyline}
                                </span>
                              </div>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )
                          ) : (
                            // NBA/NCAAB: Show live spread
                            game.spread ? (
                              <div className="flex flex-col items-center">
                                <span className="text-xs text-gray-400">{game.spread_team || game.home_team}</span>
                                {(() => {
                                  // Use helper function to determine if spread_team is home or away
                                  const isHome = isSpreadTeamHome(game.spread_team, game.home_team, game.away_team);
                                  const displaySpread = isHome ? game.spread : -game.spread;
                                  return (
                                    <span className={`font-bold ${displaySpread < 0 ? 'text-red-400' : 'text-green-400'}`}>
                                      {displaySpread > 0 ? '+' : ''}{displaySpread}
                                    </span>
                                  );
                                })()}
                              </div>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )
                          )}
                        </td>
                      )}
                      <td className="py-3 px-2 text-center">
                        {(() => {
                          // For NHL, check for 1st Period bets first
                          const firstPeriodBet = league === 'NHL' ? findFirstPeriodBetsForGame(game, firstPeriodBets, data.date) : null;
                          
                          // Render 1st Period bet info for NHL if exists
                          if (firstPeriodBet && (firstPeriodBet.u15 || firstPeriodBet.u25 || firstPeriodBet.u35 || firstPeriodBet.u45)) {
                            const bets = [];
                            if (firstPeriodBet.u15) bets.push({ line: 'u1.5', ...firstPeriodBet.u15 });
                            if (firstPeriodBet.u25) bets.push({ line: 'u2.5', ...firstPeriodBet.u25 });
                            if (firstPeriodBet.u35) bets.push({ line: 'u3.5', ...firstPeriodBet.u35 });
                            if (firstPeriodBet.u45) bets.push({ line: 'u4.5', ...firstPeriodBet.u45 });
                            
                            return (
                              <div className="flex flex-col gap-1">
                                {bets.map((bet, idx) => {
                                  const isWin = bet.result === 'win';
                                  const isLoss = bet.result === 'loss';
                                  const isPending = !bet.result || bet.result === 'pending';
                                  
                                  return (
                                    <div key={idx} className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                                      isWin ? 'bg-green-500/20 text-green-400' : 
                                      isLoss ? 'bg-red-500/20 text-red-400' : 
                                      'bg-yellow-500/20 text-yellow-400'
                                    }`}>
                                      <div className="flex items-center justify-center gap-1">
                                        {isWin ? '✓' : isLoss ? '✗' : '⏳'} {bet.line} - ${bet.risk?.toLocaleString()} / {isPending ? '$ ???' : (isWin ? `$${bet.win?.toLocaleString()}` : `-$${bet.risk?.toLocaleString()}`)}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            );
                          }
                          
                          // Original logic for non-NHL or NHL without 1st period bets
                          if (isHistorical || game.final_score) {
                            // For historical dates OR completed games with user bets: show user's bet result (HIT/MISS)
                            if (game.user_bet) {
                              return (
                                <div className="flex flex-col items-center gap-1">
                                  {/* Show what the user BET on (bet_type), then show if it was HIT/MISS/PUSH */}
                                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                                    game.bet_type?.toUpperCase()?.includes('OVER') ? 'bg-green-500/20 text-green-400' : 
                                    game.bet_type?.toUpperCase()?.includes('UNDER') ? 'bg-orange-500/20 text-orange-400' : 
                                    'bg-gray-500/20 text-gray-400'
                                  }`}>
                                    {game.bet_type?.toUpperCase()?.includes('OVER') ? '⬆️ OVER' : 
                                     game.bet_type?.toUpperCase()?.includes('UNDER') ? '⬇️ UNDER' : 
                                     game.bet_type || '-'}
                                  </span>
                                  {/* Show individual bet results if multiple bets */}
                                  {game.bet_results && game.bet_results.length > 1 ? (
                                    <div className="flex flex-col gap-0.5">
                                      {game.bet_results.map((br, idx) => (
                                        <span key={idx} className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                                          br.hit ? 'bg-green-500/30 text-green-400' : 'bg-red-500/30 text-red-400'
                                        }`}>
                                          {br.hit ? '✅' : '❌'} {br.type}
                                        </span>
                                      ))}
                                    </div>
                                  ) : (
                                    /* Single bet - show HIT/MISS status */
                                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                                      isSpreadBet 
                                        ? (game.user_bet_hit === true
                                            ? 'bg-purple-500/30 text-purple-300 ring-1 ring-purple-400/50'
                                            : game.user_bet_hit === false
                                              ? 'bg-purple-900/30 text-purple-400 ring-1 ring-purple-500/30'
                                              : 'bg-gray-500/30 text-gray-400')
                                        : (game.user_bet_hit === true
                                            ? 'bg-green-500/30 text-green-400'
                                            : game.user_bet_hit === false
                                              ? 'bg-red-500/30 text-red-400'
                                              : 'bg-gray-500/30 text-gray-400')
                                    }`}>
                                      {isSpreadBet ? (
                                        game.user_bet_hit === true ? '✅ HIT' : game.user_bet_hit === false ? '❌ MISS' : game.bet_result === 'push' ? '⚪ PUSH' : '⏳'
                                      ) : (
                                        game.user_bet_hit === true ? '✅ HIT' : game.user_bet_hit === false ? '❌ MISS' : game.bet_result === 'push' ? '⚪ PUSH' : '⏳'
                                      )}
                                    </span>
                                  )}
                                </div>
                              );
                            } else if (game.has_bet && game.bet_type) {
                              // For historical dates with has_bet but no user_bet (e.g., TIPSTER account bets) - show as pending
                              return (
                                <span className="px-2 py-1 rounded text-xs font-bold bg-gray-500/30 text-gray-400">
                                  ⏳ {game.bet_account === 'jac083' ? 'TIPSTER' : 'PENDING'}
                                </span>
                              );
                            } else if (isNoBet) {
                              // For historical dates without user bet and low edge: show NO BET
                              return (
                                <span className="px-2 py-1 rounded text-xs font-bold bg-gray-500/20 text-gray-400">
                                  ⚪ NO BET
                                </span>
                              );
                            } else if (game.recommendation) {
                              // For historical dates without user bet but with edge: show system result
                              return (
                                <span className={`px-2 py-1 rounded text-xs font-bold ${
                                  game.result_hit === true
                                    ? 'bg-green-500/30 text-green-400'
                                    : game.result_hit === false
                                      ? 'bg-red-500/30 text-red-400'
                                      : 'bg-gray-500/30 text-gray-400'
                                }`}>
                                  {game.result_hit === true ? '✅ HIT' : game.result_hit === false ? '❌ MISS' : game.result === 'PUSH' ? '⚪ PUSH' : '⏳ PENDING'}
                                </span>
                              );
                            } else {
                              return <span className="text-muted-foreground">-</span>;
                            }
                          } else if (game.has_bet && (game.bet_types?.length > 0 || game.bet_type)) {
                            // For today/tomorrow with active bet: show the bet type(s)
                            const betTypes = (game.bet_types && game.bet_types.length > 0) ? game.bet_types : (game.bet_type ? [game.bet_type] : []);
                            const uniqueTypes = [...new Set(betTypes)];
                            const typeCounts = {};
                            betTypes.forEach(t => { typeCounts[t] = (typeCounts[t] || 0) + 1; });
                            
                            // Check if this is NHL 1st Period bet
                            const isNHL1stPeriod = league === 'NHL' && betTypes.some(t => 
                              t?.toLowerCase()?.includes('total') && 
                              (t?.includes('u1.5') || t?.includes('u2.5') || t?.includes('u3.5') || t?.includes('u4.5') ||
                               t?.includes('U1.5') || t?.includes('U2.5') || t?.includes('U3.5') || t?.includes('U4.5'))
                            );
                            
                            if (isNHL1stPeriod) {
                              // Format NHL 1st Period bets specially
                              return (
                                <div className="flex flex-col gap-1">
                                  {uniqueTypes.map((betType, idx) => {
                                    // Extract the line (u1.5, u2.5, etc.)
                                    const lineMatch = betType?.match(/[uU](\d\.?\d?)/);
                                    const line = lineMatch ? `u${lineMatch[1]}` : betType;
                                    const count = typeCounts[betType];
                                    
                                    return (
                                      <div key={idx} className="px-2 py-0.5 rounded text-[10px] font-medium bg-yellow-500/20 text-yellow-400">
                                        <div className="flex items-center justify-center gap-1">
                                          ⏳ {line} / $???{count > 1 ? ` x${count}` : ''}
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              );
                            }
                            
                            // Default format for non-1st period bets
                            return (
                              <div className="flex flex-col gap-1">
                                {uniqueTypes.map((betType, idx) => {
                                  const count = typeCounts[betType];
                                  const isOver = betType?.toLowerCase()?.includes('over') || betType?.toLowerCase()?.startsWith('o');
                                  const isUnder = betType?.toLowerCase()?.includes('under') || betType?.toLowerCase()?.startsWith('u');
                                  const isSpread = !isOver && !isUnder;
                                  
                                  return (
                                    <span key={idx} className={`px-2 py-0.5 rounded text-xs font-bold ${
                                      isOver 
                                        ? 'bg-green-500/30 text-green-400' 
                                        : isUnder
                                          ? 'bg-orange-500/30 text-orange-400'
                                          : 'bg-purple-500/30 text-purple-400'
                                    }`}>
                                      {isOver ? '⬆️' : isUnder ? '⬇️' : '📊'} {betType}{count > 1 ? ` x${count}` : ''}
                                    </span>
                                  );
                                })}
                              </div>
                            );
                          } else if (isNoBet) {
                            // For today/tomorrow: show "-" for No Bet games
                            return <span className="text-muted-foreground">-</span>;
                          } else if (game.recommendation) {
                            // For today/tomorrow: show OVER/UNDER recommendation only if edge meets threshold
                            return (
                              <span className={`px-2 py-1 rounded text-xs font-bold ${
                                game.recommendation === 'OVER' 
                                  ? 'bg-blue-500/30 text-blue-400' 
                                  : 'bg-orange-500/30 text-orange-400'
                              }`}>
                                {game.recommendation === 'OVER' ? '⬆️' : '⬇️'} {game.recommendation}
                              </span>
                            );
                          } else {
                            return <span className="text-muted-foreground">-</span>;
                          }
                        })()}
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
              <p className="text-sm mt-2">Click &quot;Refresh Lines &amp; Bets&quot; to load games.</p>
            </div>
          )
          })()}
        </CardContent>
      </Card>

      {/* Excel Export Links */}
      <div className="flex flex-col gap-1 text-xs p-2 bg-gray-800/50 rounded">
        <span className="text-muted-foreground text-[10px]">Copy links to download Excel:</span>
        <code className="text-blue-400 bg-gray-900 p-1 rounded text-[10px] break-all select-all cursor-text">
          {BACKEND_URL}/api/export/excel?league=NBA&start_date=2025-12-22
        </code>
        <code className="text-blue-400 bg-gray-900 p-1 rounded text-[10px] break-all select-all cursor-text">
          {BACKEND_URL}/api/export/excel?league=NHL&start_date=2025-12-22
        </code>
        <code className="text-blue-400 bg-gray-900 p-1 rounded text-[10px] break-all select-all cursor-text">
          {BACKEND_URL}/api/export/excel?league=NCAAB&start_date=2025-12-22
        </code>
      </div>

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
              {league === 'NCAAB' && (
                <div className="flex items-center gap-2">
                  <span>🎰</span>
                  <span className="text-purple-400">Spread bet placed</span>
                </div>
              )}
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

      {/* Fade The Public Compound Records Modal */}
      {showCompoundModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={() => setShowCompoundModal(false)}>
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-cyan-400">📊 {league} Fade The Public Breakdown</h2>
              <button 
                onClick={() => setShowCompoundModal(false)}
                className="text-gray-400 hover:text-white text-2xl"
              >
                ×
              </button>
            </div>
            <p className="text-sm text-gray-400 mb-4">
              Higher fade win % = Better opportunity to bet AGAINST the public
            </p>
            
            {loadingCompound ? (
              <div className="text-center py-8 text-gray-400">Loading...</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left py-2 px-3 text-gray-400">Range</th>
                      <th className="text-center py-2 px-3 text-gray-400">Fade Record</th>
                      <th className="text-center py-2 px-3 text-gray-400">Fade Win%</th>
                      <th className="text-center py-2 px-3 text-gray-400">Games</th>
                    </tr>
                  </thead>
                  <tbody>
                    {compoundRecords.map((record, idx) => {
                      const isHot = record.fade_win_pct >= 60;
                      const isGood = record.fade_win_pct >= 55;
                      return (
                        <tr 
                          key={idx} 
                          className={`border-b border-gray-800 hover:bg-gray-800/50 cursor-pointer ${isHot ? 'bg-green-900/20' : isGood ? 'bg-green-900/10' : ''}`}
                          onClick={() => {
                            setPublicThreshold(record.low);
                            setShowCompoundModal(false);
                          }}
                        >
                          <td className="py-2 px-3 font-medium">{record.range}</td>
                          <td className="py-2 px-3 text-center">
                            <span className="text-green-400">{record.fade_wins}</span>
                            <span className="text-gray-500 mx-1">-</span>
                            <span className="text-red-400">{record.fade_losses}</span>
                          </td>
                          <td className={`py-2 px-3 text-center font-bold ${isHot ? 'text-green-400' : isGood ? 'text-green-300' : record.fade_win_pct < 45 ? 'text-red-400' : 'text-gray-300'}`}>
                            {record.fade_win_pct}%
                            {isHot && ' 🔥'}
                            {isGood && !isHot && ' ✅'}
                          </td>
                          <td className="py-2 px-3 text-center text-gray-400">{record.total_games}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            
            <div className="mt-4 pt-4 border-t border-gray-700 text-xs text-gray-500">
              <p>🔥 = 60%+ fade win rate | ✅ = 55%+ fade win rate</p>
              <p className="mt-1">Click a row to set that threshold range</p>
            </div>
          </div>
        </div>
      )}

      {/* NHL 1st Period Goals Breakdown Modal */}
      {showFirstPeriodModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={() => { setShowFirstPeriodModal(false); setExpanded4Goals(false); setExpanded5Goals(false); }}>
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-red-400">🏒 NHL 1st Period Goals Breakdown</h2>
              <button 
                onClick={() => { setShowFirstPeriodModal(false); setExpanded4Goals(false); setExpanded5Goals(false); }}
                className="text-gray-400 hover:text-white text-2xl"
              >
                ×
              </button>
            </div>
            <p className="text-sm text-gray-400 mb-4">
              Total goals scored in the 1st period across all NHL games this season (2025-2026)
            </p>
            
            {loadingFirstPeriodBreakdown ? (
              <div className="text-center py-8 text-gray-400">Loading...</div>
            ) : (() => {
              // Calculate totals and percentages
              const group02 = firstPeriodBreakdown.filter(r => r.goals <= 2);
              const row3 = firstPeriodBreakdown.find(r => r.goals === 3);
              const group45 = firstPeriodBreakdown.filter(r => r.goals >= 4);
              
              const total02 = group02.reduce((sum, r) => sum + r.total, 0);
              const l3_02 = group02.reduce((sum, r) => sum + r.l3, 0);
              const l5_02 = group02.reduce((sum, r) => sum + r.l5, 0);
              
              const total03 = total02 + (row3?.total || 0);
              const l3_03 = l3_02 + (row3?.l3 || 0);
              const l5_03 = l5_02 + (row3?.l5 || 0);
              
              const total45 = group45.reduce((sum, r) => sum + r.total, 0);
              const l3_45 = group45.reduce((sum, r) => sum + r.l3, 0);
              const l5_45 = group45.reduce((sum, r) => sum + r.l5, 0);
              
              const grandTotal = total03 + total45;
              const pct02 = grandTotal > 0 ? ((total02 / grandTotal) * 100).toFixed(1) : 0;
              const pct03 = grandTotal > 0 ? ((total03 / grandTotal) * 100).toFixed(1) : 0;
              const pct45 = grandTotal > 0 ? ((total45 / grandTotal) * 100).toFixed(1) : 0;
              
              return (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-700">
                        <th className="text-left py-2 px-3 text-gray-400">Goals</th>
                        <th className="text-center py-2 px-3 text-gray-400">Total</th>
                        <th className="text-center py-2 px-3 text-gray-400">L3</th>
                        <th className="text-center py-2 px-3 text-gray-400">L5</th>
                      </tr>
                    </thead>
                    <tbody>
                      {/* Group 1: 0-2 Goals */}
                      {group02.map((row, idx) => {
                        const isZero = row.goals === 0;
                        return (
                          <tr 
                            key={idx} 
                            className={`border-b border-gray-800 ${isZero ? 'bg-red-900/20' : 'hover:bg-gray-800/50'}`}
                          >
                            <td className={`py-2 px-3 font-medium ${isZero ? 'text-red-400' : 'text-white'}`}>
                              {row.goals === 0 ? '0-0' : row.label}
                            </td>
                            <td className={`py-2 px-3 text-center font-bold ${isZero ? 'text-red-400' : 'text-white'}`}>
                              {row.total}
                            </td>
                            <td className="py-2 px-3 text-center text-yellow-400">
                              {row.l3}
                            </td>
                            <td className="py-2 px-3 text-center text-orange-400">
                              {row.l5}
                            </td>
                          </tr>
                        );
                      })}
                      {/* Subtotal 0-2 */}
                      <tr className="bg-blue-900/30 border-b-2 border-blue-500/50">
                        <td className="py-2 px-3 font-bold text-blue-400">📊 0-2 Goals</td>
                        <td className="py-2 px-3 text-center font-bold text-blue-400 text-lg">{total02}</td>
                        <td className="py-2 px-3 text-center font-bold text-blue-300">{l3_02}</td>
                        <td className="py-2 px-3 text-center font-bold text-blue-300">{l5_02}</td>
                      </tr>
                      <tr>
                        <td colSpan="4" className="py-1 text-center text-blue-400 font-bold">{pct02}% of all games</td>
                      </tr>
                      
                      {/* Spacer */}
                      <tr><td colSpan="4" className="py-2"></td></tr>
                      
                      {/* 3 Goals Row */}
                      {row3 && (
                        <tr className="border-b border-gray-800 hover:bg-gray-800/50">
                          <td className="py-2 px-3 font-medium text-white">{row3.label}</td>
                          <td className="py-2 px-3 text-center font-bold text-white">{row3.total}</td>
                          <td className="py-2 px-3 text-center text-yellow-400">{row3.l3}</td>
                          <td className="py-2 px-3 text-center text-orange-400">{row3.l5}</td>
                        </tr>
                      )}
                      {/* Subtotal 0-3 */}
                      <tr className="bg-green-900/30 border-b-2 border-green-500/50">
                        <td className="py-2 px-3 font-bold text-green-400">📊 0-3 Goals</td>
                        <td className="py-2 px-3 text-center font-bold text-green-400 text-lg">{total03}</td>
                        <td className="py-2 px-3 text-center font-bold text-green-300">{l3_03}</td>
                        <td className="py-2 px-3 text-center font-bold text-green-300">{l5_03}</td>
                      </tr>
                      <tr>
                        <td colSpan="4" className="py-1 text-center text-green-400 font-bold">{pct03}% of all games</td>
                      </tr>
                      
                      {/* Spacer */}
                      <tr><td colSpan="4" className="py-2"></td></tr>
                      
                      {/* 4 Goals Row - Expandable */}
                      {group45.filter(r => r.goals === 4).map((row) => (
                        <React.Fragment key="4goals">
                          <tr 
                            className="border-b border-gray-800 hover:bg-gray-800/50 cursor-pointer"
                            onClick={() => setExpanded4Goals(!expanded4Goals)}
                          >
                            <td className="py-2 px-3 font-medium text-white flex items-center gap-2">
                              <span className={`transition-transform ${expanded4Goals ? 'rotate-90' : ''}`}>▶</span>
                              {row.label}
                            </td>
                            <td className="py-2 px-3 text-center font-bold text-white">{row.total}</td>
                            <td className="py-2 px-3 text-center text-yellow-400">{row.l3}</td>
                            <td className="py-2 px-3 text-center text-orange-400">{row.l5}</td>
                          </tr>
                          {expanded4Goals && teams4Goals.length > 0 && (
                            <tr>
                              <td colSpan="4" className="p-0">
                                <div className="bg-gray-800/50 p-3 mx-2 mb-2 rounded-lg">
                                  <div className="text-xs text-gray-400 mb-2 font-medium">Teams in 4-goal 1st periods:</div>
                                  <div className="grid grid-cols-2 gap-1 text-xs">
                                    {teams4Goals.slice(0, 10).map((t, i) => (
                                      <div key={i} className="flex justify-between px-2 py-1 bg-gray-700/50 rounded">
                                        <span className="text-white">{t.team}</span>
                                        <span className="text-cyan-400 font-bold">{t.count}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      ))}
                      
                      {/* 5+ Goals Row - Expandable */}
                      {group45.filter(r => r.goals === 5).map((row) => (
                        <React.Fragment key="5goals">
                          <tr 
                            className="border-b border-gray-800 hover:bg-gray-800/50 cursor-pointer"
                            onClick={() => setExpanded5Goals(!expanded5Goals)}
                          >
                            <td className="py-2 px-3 font-medium text-white flex items-center gap-2">
                              <span className={`transition-transform ${expanded5Goals ? 'rotate-90' : ''}`}>▶</span>
                              {row.label}
                            </td>
                            <td className="py-2 px-3 text-center font-bold text-white">{row.total}</td>
                            <td className="py-2 px-3 text-center text-yellow-400">{row.l3}</td>
                            <td className="py-2 px-3 text-center text-orange-400">{row.l5}</td>
                          </tr>
                          {expanded5Goals && teams5Goals.length > 0 && (
                            <tr>
                              <td colSpan="4" className="p-0">
                                <div className="bg-gray-800/50 p-3 mx-2 mb-2 rounded-lg">
                                  <div className="text-xs text-gray-400 mb-2 font-medium">Teams in 5+ goal 1st periods:</div>
                                  <div className="grid grid-cols-2 gap-1 text-xs">
                                    {teams5Goals.slice(0, 10).map((t, i) => (
                                      <div key={i} className="flex justify-between px-2 py-1 bg-gray-700/50 rounded">
                                        <span className="text-white">{t.team}</span>
                                        <span className="text-cyan-400 font-bold">{t.count}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      ))}
                      
                      {/* Subtotal 4-5+ */}
                      <tr className="bg-red-900/30 border-b-2 border-red-500/50">
                        <td className="py-2 px-3 font-bold text-red-400">📊 4-5+ Goals</td>
                        <td className="py-2 px-3 text-center font-bold text-red-400 text-lg">{total45}</td>
                        <td className="py-2 px-3 text-center font-bold text-red-300">{l3_45}</td>
                        <td className="py-2 px-3 text-center font-bold text-red-300">{l5_45}</td>
                      </tr>
                      <tr>
                        <td colSpan="4" className="py-1 text-center text-red-400 font-bold">{pct45}% of all games</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              );
            })()}
            
            <div className="mt-4 pt-4 border-t border-gray-700 text-xs text-gray-500">
              <p>🟢 0-3 = Best hit rate (89.7%) | 🔵 0-2 = Good hit rate (76.2%) | 🔴 4-5+ = Risky (10.3%)</p>
              <p className="mt-1">▶ Click on 4 Goals or 5+ Goals to see team breakdown</p>
              <p className="mt-1">Data updates automatically at 11 PM Arizona time</p>
            </div>
          </div>
        </div>
      )}

      {/* NHL 1st Period Bets Modal */}
      {showFirstPeriodBetsModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={() => setShowFirstPeriodBetsModal(false)}>
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-5xl w-full mx-4 max-h-[85vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-purple-400">💰 1st Period Bets - ENANO Record</h2>
              <button 
                onClick={() => setShowFirstPeriodBetsModal(false)}
                className="text-gray-400 hover:text-white text-2xl"
              >
                ×
              </button>
            </div>
            <p className="text-sm text-gray-400 mb-4">
              NHL 1st Period Under bets placed by ENANO (Jac075) - 2025-2026 Season
            </p>
            
            {loadingFirstPeriodBets ? (
              <div className="text-center py-8 text-gray-400">Loading bets from plays888.co...</div>
            ) : (
              <>
                {/* Summary by line */}
                <div className="grid grid-cols-5 gap-3 mb-6">
                  <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                    <div className="text-xs text-gray-400">TOTAL</div>
                    <div className="text-lg font-bold">
                      <span className="text-green-400">{firstPeriodBets.summary?.total?.wins || 0}</span>
                      <span className="text-gray-500 mx-1">-</span>
                      <span className="text-red-400">{firstPeriodBets.summary?.total?.losses || 0}</span>
                    </div>
                    <div className={`text-xs font-bold ${(firstPeriodBets.summary?.total?.profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(firstPeriodBets.summary?.total?.profit || 0) >= 0 ? '+' : ''}${(firstPeriodBets.summary?.total?.profit || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </div>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                    <div className="text-xs text-gray-400">Under 1.5</div>
                    <div className="text-lg font-bold">
                      <span className="text-green-400">{firstPeriodBets.summary?.u15?.wins || 0}</span>
                      <span className="text-gray-500 mx-1">-</span>
                      <span className="text-red-400">{firstPeriodBets.summary?.u15?.losses || 0}</span>
                    </div>
                    <div className={`text-xs font-bold ${(firstPeriodBets.summary?.u15?.profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(firstPeriodBets.summary?.u15?.profit || 0) >= 0 ? '+' : ''}${(firstPeriodBets.summary?.u15?.profit || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </div>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                    <div className="text-xs text-gray-400">Under 2.5</div>
                    <div className="text-lg font-bold">
                      <span className="text-green-400">{firstPeriodBets.summary?.u25?.wins || 0}</span>
                      <span className="text-gray-500 mx-1">-</span>
                      <span className="text-red-400">{firstPeriodBets.summary?.u25?.losses || 0}</span>
                    </div>
                    <div className={`text-xs font-bold ${(firstPeriodBets.summary?.u25?.profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(firstPeriodBets.summary?.u25?.profit || 0) >= 0 ? '+' : ''}${(firstPeriodBets.summary?.u25?.profit || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </div>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                    <div className="text-xs text-gray-400">Under 3.5</div>
                    <div className="text-lg font-bold">
                      <span className="text-green-400">{firstPeriodBets.summary?.u35?.wins || 0}</span>
                      <span className="text-gray-500 mx-1">-</span>
                      <span className="text-red-400">{firstPeriodBets.summary?.u35?.losses || 0}</span>
                    </div>
                    <div className={`text-xs font-bold ${(firstPeriodBets.summary?.u35?.profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(firstPeriodBets.summary?.u35?.profit || 0) >= 0 ? '+' : ''}${(firstPeriodBets.summary?.u35?.profit || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </div>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                    <div className="text-xs text-gray-400">Under 4.5</div>
                    <div className="text-lg font-bold">
                      <span className="text-green-400">{firstPeriodBets.summary?.u45?.wins || 0}</span>
                      <span className="text-gray-500 mx-1">-</span>
                      <span className="text-red-400">{firstPeriodBets.summary?.u45?.losses || 0}</span>
                    </div>
                    <div className={`text-xs font-bold ${(firstPeriodBets.summary?.u45?.profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(firstPeriodBets.summary?.u45?.profit || 0) >= 0 ? '+' : ''}${(firstPeriodBets.summary?.u45?.profit || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </div>
                  </div>
                </div>

                {/* Bets table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-700">
                        <th className="text-left py-2 px-2 text-gray-400">Date</th>
                        <th className="text-left py-2 px-2 text-gray-400">Game</th>
                        <th className="text-center py-2 px-2 text-gray-400">U1.5</th>
                        <th className="text-center py-2 px-2 text-gray-400">U2.5</th>
                        <th className="text-center py-2 px-2 text-gray-400">U3.5</th>
                        <th className="text-center py-2 px-2 text-gray-400">U4.5</th>
                        <th className="text-center py-2 px-2 text-gray-400">Bet</th>
                        <th className="text-center py-2 px-2 text-gray-400">Result</th>
                      </tr>
                    </thead>
                    <tbody>
                      {firstPeriodBets.bets?.length > 0 ? (
                        firstPeriodBets.bets.map((bet, idx) => (
                          <tr key={idx} className="border-b border-gray-800 hover:bg-gray-800/50">
                            <td className="py-2 px-2 text-gray-300">{bet.date}</td>
                            <td className="py-2 px-2 text-white font-medium">{bet.game}</td>
                            <td className="py-2 px-2 text-center">
                              {bet.u15 ? (
                                <div className={`rounded px-2 py-1 ${bet.u15.result === 'win' ? 'bg-green-900/30' : 'bg-red-900/30'}`}>
                                  <div className={`font-bold text-xs ${bet.u15.result === 'win' ? 'text-green-400' : 'text-red-400'}`}>
                                    {bet.u15.result === 'win' ? 'WIN' : 'LOSS'}
                                  </div>
                                  <div className={`text-[10px] ${bet.u15.result === 'win' ? 'text-green-300' : 'text-red-300'}`}>
                                    ${bet.u15.risk?.toLocaleString()}→{bet.u15.result === 'win' ? '$' + bet.u15.win?.toLocaleString() : '-$' + bet.u15.risk?.toLocaleString()}
                                  </div>
                                </div>
                              ) : (
                                <span className="text-gray-600">-</span>
                              )}
                            </td>
                            <td className="py-2 px-2 text-center">
                              {bet.u25 ? (
                                <div className={`rounded px-2 py-1 ${bet.u25.result === 'win' ? 'bg-green-900/30' : 'bg-red-900/30'}`}>
                                  <div className={`font-bold text-xs ${bet.u25.result === 'win' ? 'text-green-400' : 'text-red-400'}`}>
                                    {bet.u25.result === 'win' ? 'WIN' : 'LOSS'}
                                  </div>
                                  <div className={`text-[10px] ${bet.u25.result === 'win' ? 'text-green-300' : 'text-red-300'}`}>
                                    ${bet.u25.risk?.toLocaleString()}→{bet.u25.result === 'win' ? '$' + bet.u25.win?.toLocaleString() : '-$' + bet.u25.risk?.toLocaleString()}
                                  </div>
                                </div>
                              ) : (
                                <span className="text-gray-600">-</span>
                              )}
                            </td>
                            <td className="py-2 px-2 text-center">
                              {bet.u35 ? (
                                <div className={`rounded px-2 py-1 ${bet.u35.result === 'win' ? 'bg-green-900/30' : 'bg-red-900/30'}`}>
                                  <div className={`font-bold text-xs ${bet.u35.result === 'win' ? 'text-green-400' : 'text-red-400'}`}>
                                    {bet.u35.result === 'win' ? 'WIN' : 'LOSS'}
                                  </div>
                                  <div className={`text-[10px] ${bet.u35.result === 'win' ? 'text-green-300' : 'text-red-300'}`}>
                                    ${bet.u35.risk?.toLocaleString()}→{bet.u35.result === 'win' ? '$' + bet.u35.win?.toLocaleString() : '-$' + bet.u35.risk?.toLocaleString()}
                                  </div>
                                </div>
                              ) : (
                                <span className="text-gray-600">-</span>
                              )}
                            </td>
                            <td className="py-2 px-2 text-center">
                              {bet.u45 ? (
                                <div className={`rounded px-2 py-1 ${bet.u45.result === 'win' ? 'bg-green-900/30' : 'bg-red-900/30'}`}>
                                  <div className={`font-bold text-xs ${bet.u45.result === 'win' ? 'text-green-400' : 'text-red-400'}`}>
                                    {bet.u45.result === 'win' ? 'WIN' : 'LOSS'}
                                  </div>
                                  <div className={`text-[10px] ${bet.u45.result === 'win' ? 'text-green-300' : 'text-red-300'}`}>
                                    ${bet.u45.risk?.toLocaleString()}→{bet.u45.result === 'win' ? '$' + bet.u45.win?.toLocaleString() : '-$' + bet.u45.risk?.toLocaleString()}
                                  </div>
                                </div>
                              ) : (
                                <span className="text-gray-600">-</span>
                              )}
                            </td>
                            <td className="py-2 px-2 text-center">
                              <span className="text-yellow-400 font-medium">
                                ${(bet.total_bet || 0).toLocaleString()}
                              </span>
                            </td>
                            <td className="py-2 px-2 text-center">
                              <span className={`font-bold ${(bet.result || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {(bet.result || 0) >= 0 ? '+' : ''}${Math.abs(bet.result || 0).toLocaleString()}
                              </span>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan="8" className="py-8 text-center text-gray-500">
                            No 1st Period bets found. Click "Update Scores" to refresh data from plays888.co
                          </td>
                        </tr>
                      )}
                    </tbody>
                    {/* Total footer row */}
                    {firstPeriodBets.bets?.length > 0 && (
                      <tfoot>
                        <tr className="border-t-2 border-purple-500/50 bg-purple-900/20">
                          <td colSpan="2" className="py-3 px-2 text-white font-bold">TOTAL ({firstPeriodBets.bets?.length} games)</td>
                          <td className="py-3 px-2 text-center">
                            <div className="text-xs text-gray-400">{firstPeriodBets.summary?.u15?.wins || 0}W-{firstPeriodBets.summary?.u15?.losses || 0}L</div>
                            <div className={`font-bold text-xs ${(firstPeriodBets.summary?.u15?.profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {(firstPeriodBets.summary?.u15?.profit || 0) >= 0 ? '+' : ''}${Math.abs(firstPeriodBets.summary?.u15?.profit || 0).toLocaleString()}
                            </div>
                          </td>
                          <td className="py-3 px-2 text-center">
                            <div className="text-xs text-gray-400">{firstPeriodBets.summary?.u25?.wins || 0}W-{firstPeriodBets.summary?.u25?.losses || 0}L</div>
                            <div className={`font-bold text-xs ${(firstPeriodBets.summary?.u25?.profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {(firstPeriodBets.summary?.u25?.profit || 0) >= 0 ? '+' : ''}${Math.abs(firstPeriodBets.summary?.u25?.profit || 0).toLocaleString()}
                            </div>
                          </td>
                          <td className="py-3 px-2 text-center">
                            <div className="text-xs text-gray-400">{firstPeriodBets.summary?.u35?.wins || 0}W-{firstPeriodBets.summary?.u35?.losses || 0}L</div>
                            <div className={`font-bold text-xs ${(firstPeriodBets.summary?.u35?.profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {(firstPeriodBets.summary?.u35?.profit || 0) >= 0 ? '+' : ''}${Math.abs(firstPeriodBets.summary?.u35?.profit || 0).toLocaleString()}
                            </div>
                          </td>
                          <td className="py-3 px-2 text-center">
                            <div className="text-xs text-gray-400">{firstPeriodBets.summary?.u45?.wins || 0}W-{firstPeriodBets.summary?.u45?.losses || 0}L</div>
                            <div className={`font-bold text-xs ${(firstPeriodBets.summary?.u45?.profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {(firstPeriodBets.summary?.u45?.profit || 0) >= 0 ? '+' : ''}${Math.abs(firstPeriodBets.summary?.u45?.profit || 0).toLocaleString()}
                            </div>
                          </td>
                          <td className="py-3 px-2 text-center">
                            <span className="text-yellow-400 font-bold">
                              ${firstPeriodBets.bets?.reduce((sum, b) => sum + (b.total_bet || 0), 0).toLocaleString()}
                            </span>
                          </td>
                          <td className="py-3 px-2 text-center">
                            <span className={`font-bold text-lg ${(firstPeriodBets.summary?.total?.profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {(firstPeriodBets.summary?.total?.profit || 0) >= 0 ? '+' : ''}${Math.abs(firstPeriodBets.summary?.total?.profit || 0).toLocaleString()}
                            </span>
                          </td>
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </div>
              </>
            )}
            
            <div className="mt-4 pt-4 border-t border-gray-700 text-xs text-gray-500">
              <p>💰 Data from plays888.co - Account: ENANO (Jac075)</p>
              <p className="mt-1">Click "Update Scores" button to refresh betting data</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
