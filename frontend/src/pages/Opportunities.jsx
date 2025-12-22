import { useEffect, useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw, TrendingUp, TrendingDown, Target } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Opportunities() {
  const [data, setData] = useState({ games: [], plays: [], date: '', last_updated: '' });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadOpportunities();
  }, []);

  const loadOpportunities = async () => {
    try {
      const response = await axios.get(`${API}/opportunities`);
      setData(response.data);
    } catch (error) {
      console.error('Error loading opportunities:', error);
      toast.error('Failed to load opportunities');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const response = await axios.post(`${API}/opportunities/refresh`);
      setData(response.data);
      toast.success('Opportunities refreshed!');
    } catch (error) {
      console.error('Error refreshing:', error);
      toast.error('Failed to refresh');
    } finally {
      setRefreshing(false);
    }
  };

  const getRowStyle = (color) => {
    if (color === 'green') return 'bg-green-500/20 border-green-500/50';
    if (color === 'red') return 'bg-red-500/20 border-red-500/50';
    return '';
  };

  const getTextStyle = (color) => {
    if (color === 'green') return 'text-green-400 font-bold';
    if (color === 'red') return 'text-red-400 font-bold';
    return 'text-muted-foreground';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading opportunities...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl lg:text-4xl font-heading font-bold tracking-tight flex items-center gap-2">
            <Target className="w-8 h-8 text-primary" />
            Opportunities
          </h1>
          <p className="text-sm lg:text-base text-muted-foreground mt-1">
            NBA Over/Under analysis based on PPG rankings
          </p>
        </div>
        <Button 
          onClick={handleRefresh} 
          disabled={refreshing}
          className="flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh Data
        </Button>
      </div>

      {/* Info Card */}
      <Card className="glass-card border-primary/30">
        <CardContent className="pt-4">
          <div className="flex flex-wrap gap-4 text-sm">
            <div><span className="text-muted-foreground">Date:</span> <span className="font-mono">{data.date || 'N/A'}</span></div>
            <div><span className="text-muted-foreground">Last Updated:</span> <span className="font-mono">{data.last_updated || 'N/A'}</span></div>
            <div><span className="text-muted-foreground">Games:</span> <span className="font-mono">{data.games?.length || 0}</span></div>
          </div>
        </CardContent>
      </Card>

      {/* Today's Plays */}
      {data.plays && data.plays.length > 0 && (
        <Card className="glass-card neon-border">
          <CardHeader className="border-b border-border pb-4">
            <CardTitle className="text-lg flex items-center gap-2">
              🎯 TODAY'S PLAYS
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="grid gap-3">
              {data.plays.map((play, idx) => (
                <div 
                  key={idx}
                  className={`p-4 rounded-lg border ${getRowStyle(play.color)}`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div className="flex items-center gap-3">
                      {play.recommendation === 'OVER' ? (
                        <TrendingUp className="w-6 h-6 text-green-400" />
                      ) : (
                        <TrendingDown className="w-6 h-6 text-red-400" />
                      )}
                      <div>
                        <div className="font-bold">{play.game}</div>
                        <div className="text-sm text-muted-foreground">
                          Line: {play.total} | PPG Avg: {play.combined_ppg || 'N/A'}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-xl font-bold ${getTextStyle(play.color)}`}>
                        {play.recommendation === 'OVER' ? '⬆️' : '⬇️'} {play.recommendation}
                      </div>
                      <div className="text-sm text-muted-foreground">Game Avg: {play.game_avg}</div>
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
          <CardTitle className="text-lg">NBA Games Analysis</CardTitle>
        </CardHeader>
        <CardContent className="pt-4 overflow-x-auto">
          {data.games && data.games.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-2">#</th>
                  <th className="text-left py-3 px-2">Time</th>
                  <th className="text-left py-3 px-2">Away</th>
                  <th className="text-center py-3 px-2">PPG</th>
                  <th className="text-center py-3 px-2">L3</th>
                  <th className="text-left py-3 px-2">Home</th>
                  <th className="text-center py-3 px-2">PPG</th>
                  <th className="text-center py-3 px-2">L3</th>
                  <th className="text-center py-3 px-2">Total</th>
                  <th className="text-center py-3 px-2">Avg</th>
                  <th className="text-center py-3 px-2">Bet</th>
                </tr>
              </thead>
              <tbody>
                {data.games.map((game) => (
                  <tr 
                    key={game.game_num}
                    className={`border-b border-border/50 ${getRowStyle(game.color)}`}
                  >
                    <td className="py-3 px-2 font-mono">{game.game_num}</td>
                    <td className="py-3 px-2 text-muted-foreground">{game.time}</td>
                    <td className={`py-3 px-2 font-medium ${getTextStyle(game.color)}`}>{game.away_team}</td>
                    <td className={`py-3 px-2 text-center font-mono ${getTextStyle(game.color)}`}>{game.away_ppg_rank}</td>
                    <td className={`py-3 px-2 text-center font-mono ${getTextStyle(game.color)}`}>{game.away_last3_rank}</td>
                    <td className={`py-3 px-2 font-medium ${getTextStyle(game.color)}`}>{game.home_team}</td>
                    <td className={`py-3 px-2 text-center font-mono ${getTextStyle(game.color)}`}>{game.home_ppg_rank}</td>
                    <td className={`py-3 px-2 text-center font-mono ${getTextStyle(game.color)}`}>{game.home_last3_rank}</td>
                    <td className={`py-3 px-2 text-center font-mono ${getTextStyle(game.color)}`}>{game.total}</td>
                    <td className={`py-3 px-2 text-center font-bold ${getTextStyle(game.color)}`}>{game.game_avg}</td>
                    <td className="py-3 px-2 text-center">
                      {game.recommendation ? (
                        <span className={`px-2 py-1 rounded text-xs font-bold ${
                          game.recommendation === 'OVER' 
                            ? 'bg-green-500/30 text-green-400' 
                            : 'bg-red-500/30 text-red-400'
                        }`}>
                          {game.recommendation === 'OVER' ? '⬆️' : '⬇️'} {game.recommendation}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <Target className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No opportunities data available.</p>
              <p className="text-sm mt-2">Click "Refresh Data" to load today's games.</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Legend */}
      <Card className="glass-card">
        <CardContent className="pt-4">
          <div className="text-sm">
            <div className="font-bold mb-2">Betting Rule:</div>
            <div className="flex flex-wrap gap-4">
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-green-500/30 border border-green-500/50"></span>
                <span>Game Avg 1-12.5 → <span className="text-green-400 font-bold">OVER</span></span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-muted border border-border"></span>
                <span>Game Avg 13-17 → No edge</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-red-500/30 border border-red-500/50"></span>
                <span>Game Avg 17.5-30 → <span className="text-red-400 font-bold">UNDER</span></span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
