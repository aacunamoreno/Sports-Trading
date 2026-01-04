import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw, TrendingUp, TrendingDown, Target, Wifi, Calendar, Download, Upload } from 'lucide-react';
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
  const [exporting, setExporting] = useState(false);
  const [edgeRecord, setEdgeRecord] = useState({ hits: 0, misses: 0 });
  const [updatingPPG, setUpdatingPPG] = useState(false);
  const [updatingScores, setUpdatingScores] = useState(false);
  const [updatingBetResults, setUpdatingBetResults] = useState(false);
  const [updatingRecords, setUpdatingRecords] = useState(false);
  const [rankingPPGRecord, setRankingPPGRecord] = useState({ high: { hits: 0, misses: 0 }, low: { hits: 0, misses: 0 } });

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

  const handleRefresh = async () => {
    setRefreshing(true);
    toast.info('Refreshing lines & bets from plays888.co...');
    try {
      // Use the "refresh lines & bets" endpoint that preserves PPG values and opening lines
      // Pass the current day parameter so tomorrow's games get refreshed correctly
      const response = await axios.post(`${API}/opportunities/refresh-lines?league=${league}&day=${day}`, {}, { timeout: 60000 });
      
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
                     : `/scores/ncaab/update?date=${dateStr}`;
      
      const response = await axios.post(`${API}${endpoint}`, {}, { timeout: 120000 });
      
      if (response.data.success) {
        toast.success(`Updated ${response.data.games_updated} games for ${dateStr}. Hit Rate: ${response.data.hit_rate}`);
        // Reload data to show updated scores
        await loadOpportunities();
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

  // Scrape Tomorrow's Opening Lines (8pm Job)
  const [scrapingOpeners, setScrapingOpeners] = useState(false);
  
  const handleScrapeOpeners = async () => {
    setScrapingOpeners(true);
    toast.info('Scraping tomorrow\'s opening lines...');
    try {
      // Get tomorrow's date in Arizona timezone
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const targetDate = tomorrow.toISOString().split('T')[0];
      
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
      
      // Get tomorrow's date in local timezone (not UTC)
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const targetDate = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`;
      
      // Process all 3 leagues
      toast.info('Processing PPG for all leagues...');
      
      const results = [];
      for (const lg of ['NBA', 'NHL', 'NCAAB']) {
        try {
          const response = await axios.post(
            `${API}/ppg/upload-excel?league=${lg}&target_date=${targetDate}`,
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
      
      // Refresh data if viewing tomorrow
      if (day === 'tomorrow') {
        loadOpportunities();
      }
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
  // NBA: Green if |edge| >= 5
  // NHL: Green if |edge| >= 0.5
  // NCAAB: Green if |edge| >= 9
  // A negative edge like -16.4 is a strong UNDER play, so it should be green
  const getEdgeStyle = (edge, currentLeague = league) => {
    const absEdge = Math.abs(edge);
    if (currentLeague === 'NBA') {
      if (absEdge >= 5) return 'text-green-400 font-bold';
      return 'text-red-400 font-bold';
    } else if (currentLeague === 'NCAAB') {
      if (absEdge >= 9) return 'text-green-400 font-bold';
      return 'text-red-400 font-bold';
    } else {
      // NHL
      if (absEdge >= 0.5) return 'text-green-400 font-bold';
      return 'text-red-400 font-bold';
    }
  };

  // League-specific config (NFL eliminated)
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
    NCAAB: {
      statLabel: 'PPG',
      combinedLabel: 'PPG Avg',
      overRange: '1-91',
      noEdgeRange: '92-273',
      underRange: '274-365',
      totalTeams: 365,
      edgeThreshold: 9
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
            data-testid="refresh-lines-bets-btn"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh Lines & Bets
          </Button>
        </div>
        
        {/* Row 2: Action Buttons */}
        <div className="flex flex-wrap items-center gap-2 mt-3">
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
            onClick={handleExport} 
            disabled={exporting}
            variant="outline"
            size="sm"
            className="flex items-center gap-2"
          >
            <Download className={`w-4 h-4 ${exporting ? 'animate-pulse' : ''}`} />
            {exporting ? 'Exporting...' : 'Export Excel'}
          </Button>
          {league === 'NCAAB' && day === 'tomorrow' && (
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
          {day === 'tomorrow' && (
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
          {['NBA', 'NHL', 'NCAAB'].map((l) => (
            <button
              key={l}
              onClick={() => setLeague(l)}
              className={`px-4 py-2 rounded-lg font-bold text-sm transition-all ${
                league === l
                  ? 'bg-primary text-primary-foreground shadow-lg'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
            >
              {l === 'NBA' ? '🏀' : l === 'NHL' ? '🏒' : '🎓'} {l}
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
          
          {/* Day selector for all leagues */}
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
                  const edgeThreshold = league === 'NBA' ? 5 : league === 'NCAAB' ? 9 : 0.5;
                  return g.result_hit === true && g.edge !== null && g.edge !== undefined && Math.abs(g.edge) >= edgeThreshold;
                }).length}</span></div>
                <div><span className="text-muted-foreground">Misses:</span> <span className="font-mono text-red-400">{data.games.filter(g => {
                  const edgeThreshold = league === 'NBA' ? 5 : league === 'NCAAB' ? 9 : 0.5;
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
            const isHistorical = day === 'yesterday' || day === 'custom';
            // Show historical columns if viewing past data OR if any game has final scores
            const hasAnyFinalScores = data.games && data.games.some(g => g.final_score);
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
                  {!showHistoricalColumns && <th className="text-center py-3 px-2">Open</th>}
                  <th className="text-center py-3 px-2">Line</th>
                  {showHistoricalColumns && <th className="text-center py-3 px-2">Final</th>}
                  {showHistoricalColumns && <th className="text-center py-3 px-2">Diff</th>}
                  <th className="text-center py-3 px-2">{league === 'NBA' || league === 'NCAAB' ? 'PPG' : 'GPG'} Avg</th>
                  <th className="text-center py-3 px-2">Edge</th>
                  <th className="text-center py-3 px-2">{showHistoricalColumns ? 'Result' : 'Bet'}</th>
                </tr>
              </thead>
              <tbody>
                {data.games.map((game, index) => {
                  // Check if edge is below threshold - if so, it's a "No Bet" game
                  const edgeThreshold = league === 'NBA' ? 5 : league === 'NCAAB' ? 9 : 0.5;
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
                    // Edge threshold: NBA >= 5, NHL >= 0.5, NCAAB >= 9
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
                          <span className={`w-2.5 h-2.5 rounded-full ${getDotColor(game.away_ppg_rank || game.away_gpg_rank)}`}></span>
                          <span className={`w-2.5 h-2.5 rounded-full ${getDotColor(game.away_last3_rank)}`}></span>
                          <span className={`w-2.5 h-2.5 rounded-full ${getDotColor(game.home_ppg_rank || game.home_gpg_rank)}`}></span>
                          <span className={`w-2.5 h-2.5 rounded-full ${getDotColor(game.home_last3_rank)}`}></span>
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
                      {/* Opening Line column - only for non-historical */}
                      {!showHistoricalColumns && (
                        <td className={`py-3 px-2 text-center font-mono text-muted-foreground`}>
                          {game.opening_line || game.total || '-'}
                        </td>
                      )}
                      {/* Current/Live Line column */}
                      <td className={`py-3 px-2 text-center font-mono ${textStyle}`}>
                        {(() => {
                          // For non-historical: show live_line if available, otherwise total/opening_line
                          const currentLine = game.live_line || game.total || game.opening_line;
                          const openingLine = game.opening_line || game.total;
                          const lineMovement = currentLine && openingLine ? currentLine - openingLine : 0;
                          
                          if (!currentLine) return <span className="text-gray-500 text-xs">NO LINE</span>;
                          
                          // Calculate bet line movement (if user bet, compare closing to bet line)
                          const betLineMovement = game.user_bet && game.bet_line ? currentLine - game.bet_line : 0;
                          
                          return (
                            <div className="flex flex-col">
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
                      {showHistoricalColumns && (
                        <td className={`py-3 px-2 text-center font-mono ${textStyle}`}>
                          {game.final_score || '-'}
                        </td>
                      )}
                      {showHistoricalColumns && (
                        <td className="py-3 px-2 text-center font-mono">
                          {game.final_score && game.total ? (
                            <span className={game.final_score > game.total ? 'text-green-400' : 'text-red-400'}>
                              {game.final_score > game.total ? '⬆️' : '⬇️'} {game.final_score > game.total ? '+' : ''}{(game.final_score - game.total).toFixed(1)}
                            </span>
                          ) : '-'}
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
                      <td className="py-3 px-2 text-center">
                        {(isHistorical || game.final_score) ? (
                          // For historical dates OR completed games with user bets: show user's bet result (HIT/MISS)
                          game.user_bet ? (
                            <div className="flex flex-col items-center gap-1">
                              {/* Show game result (OVER/UNDER) */}
                              <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                                game.result === 'OVER' ? 'bg-green-500/20 text-green-400' : 
                                game.result === 'UNDER' ? 'bg-orange-500/20 text-orange-400' : 
                                'bg-gray-500/20 text-gray-400'
                              }`}>
                                {game.result === 'OVER' ? '⬆️ OVER' : game.result === 'UNDER' ? '⬇️ UNDER' : game.result || '-'}
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
                          ) : game.has_bet && game.bet_type ? (
                            // For historical dates with has_bet but no user_bet (e.g., TIPSTER account bets) - show as pending
                            <span className="px-2 py-1 rounded text-xs font-bold bg-gray-500/30 text-gray-400">
                              ⏳ {game.bet_account === 'jac083' ? 'TIPSTER' : 'PENDING'}
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
                              {game.result_hit === true ? '✅ HIT' : game.result_hit === false ? '❌ MISS' : game.result === 'PUSH' ? '⚪ PUSH' : '⏳ PENDING'}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )
                        ) : game.has_bet && (game.bet_types?.length > 0 || game.bet_type) ? (
                          // For today/tomorrow with active bet: show the bet type(s)
                          <div className="flex flex-col gap-1">
                            {/* Get unique bet types */}
                            {(() => {
                              const betTypes = (game.bet_types && game.bet_types.length > 0) ? game.bet_types : (game.bet_type ? [game.bet_type] : []);
                              const uniqueTypes = [...new Set(betTypes)];
                              const typeCounts = {};
                              betTypes.forEach(t => { typeCounts[t] = (typeCounts[t] || 0) + 1; });
                              
                              return uniqueTypes.map((betType, idx) => {
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
                              });
                            })()}
                          </div>
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
    </div>
  );
}
