import { useEffect, useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Activity, TrendingUp, Target, DollarSign } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [recentBets, setRecentBets] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const [statsRes, betsRes] = await Promise.all([
        axios.get(`${API}/stats`),
        axios.get(`${API}/bets/history`),
      ]);
      setStats(statsRes.data);
      setRecentBets(betsRes.data.slice(0, 5));
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  // Mock chart data
  const chartData = [
    { date: 'Mon', profit: 0 },
    { date: 'Tue', profit: 0 },
    { date: 'Wed', profit: 0 },
    { date: 'Thu', profit: 0 },
    { date: 'Fri', profit: 0 },
    { date: 'Sat', profit: 0 },
    { date: 'Sun', profit: 0 },
  ];

  if (loading) {
    return <div className="text-center text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-4xl font-heading font-bold tracking-tight mb-2" data-testid="dashboard-title">
          Control Room
        </h1>
        <p className="text-muted-foreground">Monitor your automated betting operations</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="glass-card neon-border" data-testid="stat-total-bets">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
              Total Bets
            </CardTitle>
            <Activity className="w-4 h-4 text-primary" strokeWidth={1.5} />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-mono font-bold text-primary">{stats?.total_bets || 0}</div>
          </CardContent>
        </Card>

        <Card className="glass-card neon-border" data-testid="stat-active-rules">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
              Active Rules
            </CardTitle>
            <Target className="w-4 h-4 text-primary" strokeWidth={1.5} />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-mono font-bold text-primary">{stats?.active_rules || 0}</div>
          </CardContent>
        </Card>

        <Card className="glass-card neon-border" data-testid="stat-win-rate">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
              Win Rate
            </CardTitle>
            <TrendingUp className="w-4 h-4 text-primary" strokeWidth={1.5} />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-mono font-bold text-primary">{stats?.win_rate || 0}%</div>
          </CardContent>
        </Card>

        <Card className="glass-card neon-border" data-testid="stat-total-profit">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
              Total P/L
            </CardTitle>
            <DollarSign className="w-4 h-4 text-primary" strokeWidth={1.5} />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-mono font-bold text-primary">${stats?.total_profit || 0}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart */}
        <Card className="glass-card neon-border lg:col-span-2" data-testid="profit-chart">
          <CardHeader className="border-b border-border">
            <CardTitle className="font-heading text-lg">Profit/Loss Over Time</CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="date" stroke="hsl(var(--muted-foreground))" className="font-mono text-xs" />
                <YAxis stroke="hsl(var(--muted-foreground))" className="font-mono text-xs" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--muted))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '0.125rem',
                  }}
                  labelClassName="font-mono"
                />
                <Line
                  type="monotone"
                  dataKey="profit"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={{ fill: 'hsl(var(--primary))' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Activity Log */}
        <Card className="glass-card neon-border" data-testid="activity-log">
          <CardHeader className="border-b border-border">
            <CardTitle className="font-heading text-lg">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="space-y-3">
              {recentBets.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">No recent activity</p>
              ) : (
                recentBets.map((bet) => (
                  <div key={bet.id} className="flex items-center justify-between py-2 border-b border-border/50">
                    <div>
                      <div className="text-sm font-medium">Bet Placed</div>
                      <div className="text-xs font-mono text-muted-foreground">
                        ${bet.wager_amount}
                      </div>
                    </div>
                    <div className={`text-xs font-mono px-2 py-1 rounded-sm ${
                      bet.status === 'placed' ? 'bg-primary/20 text-primary' :
                      bet.status === 'won' ? 'bg-green-500/20 text-green-400' :
                      'bg-destructive/20 text-destructive'
                    }`}>
                      {bet.status.toUpperCase()}
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
