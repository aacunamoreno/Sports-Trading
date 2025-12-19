import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Activity, TrendingUp, TrendingDown, DollarSign, RefreshCw, User, ChevronLeft, ChevronRight } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Dashboard() {
  const [accounts, setAccounts] = useState([]);
  const [selectedAccountIndex, setSelectedAccountIndex] = useState(0);
  const [accountSummary, setAccountSummary] = useState(null);
  const [stats, setStats] = useState(null);
  const [recentBets, setRecentBets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(false);

  const [allSummaries, setAllSummaries] = useState({});

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const [statsRes, betsRes, accountsRes, summariesRes] = await Promise.all([
        axios.get(`${API}/stats`),
        axios.get(`${API}/bets/history`),
        axios.get(`${API}/accounts`),
        axios.get(`${API}/accounts/all/summaries`),
      ]);
      setStats(statsRes.data);
      setRecentBets(betsRes.data.slice(0, 5));
      setAccounts(accountsRes.data.accounts || []);
      
      // Store all summaries in a map for quick access
      const summariesMap = {};
      (summariesRes.data.summaries || []).forEach(s => {
        summariesMap[s.username] = s;
      });
      setAllSummaries(summariesMap);
      
      // Set first account's summary
      if (accountsRes.data.accounts && accountsRes.data.accounts.length > 0) {
        const firstUsername = accountsRes.data.accounts[0].username;
        setAccountSummary(summariesMap[firstUsername] || null);
      }
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadAccountSummary = useCallback(async (username) => {
    setSummaryLoading(true);
    try {
      const response = await axios.get(`${API}/accounts/${username}/summary`);
      setAccountSummary(response.data);
    } catch (error) {
      console.error('Error loading account summary:', error);
      setAccountSummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  const handlePrevAccount = () => {
    const newIndex = selectedAccountIndex > 0 ? selectedAccountIndex - 1 : accounts.length - 1;
    setSelectedAccountIndex(newIndex);
    if (accounts[newIndex]) {
      loadAccountSummary(accounts[newIndex].username);
    }
  };

  const handleNextAccount = () => {
    const newIndex = selectedAccountIndex < accounts.length - 1 ? selectedAccountIndex + 1 : 0;
    setSelectedAccountIndex(newIndex);
    if (accounts[newIndex]) {
      loadAccountSummary(accounts[newIndex].username);
    }
  };

  const handleRefresh = () => {
    if (accounts[selectedAccountIndex]) {
      loadAccountSummary(accounts[selectedAccountIndex].username);
    }
  };

  // Day display names
  const dayDisplayNames = {
    'mon': 'Mon', 'tue': 'Tue', 'wed': 'Wed',
    'thu': 'Thu', 'fri': 'Fri', 'sat': 'Sat', 'sun': 'Sun'
  };

  // Prepare chart data from account summary
  const chartData = accountSummary?.daily_profits?.map(d => ({
    day: dayDisplayNames[d.day] || d.day,
    profit: d.profit,
    isToday: d.day === accountSummary?.today_day
  })) || [
    { day: 'Mon', profit: 0 },
    { day: 'Tue', profit: 0 },
    { day: 'Wed', profit: 0 },
    { day: 'Thu', profit: 0 },
    { day: 'Fri', profit: 0 },
    { day: 'Sat', profit: 0 },
    { day: 'Sun', profit: 0 },
  ];

  if (loading) {
    return <div className="text-center text-muted-foreground py-12">Loading...</div>;
  }

  const currentAccount = accounts[selectedAccountIndex];
  const todayProfit = accountSummary?.today_profit || 0;
  const weekTotal = accountSummary?.week_total || 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-4xl font-heading font-bold tracking-tight mb-2" data-testid="dashboard-title">
          Control Room
        </h1>
        <p className="text-muted-foreground">Monitor your automated betting operations</p>
      </div>

      {/* Account Selector Card */}
      {accounts.length > 0 && (
        <Card className="glass-card neon-border">
          <CardHeader className="border-b border-border pb-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <User className="w-5 h-5 text-primary" />
                <CardTitle className="font-heading text-lg">Account Summary</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handlePrevAccount}
                  className="p-2 hover:bg-muted rounded-md transition-colors disabled:opacity-50"
                  disabled={accounts.length <= 1}
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <div className="min-w-[120px] text-center">
                  <span className="font-mono font-bold text-primary text-lg">
                    {currentAccount?.label || 'No Account'}
                  </span>
                  <div className="text-xs text-muted-foreground">
                    {selectedAccountIndex + 1} of {accounts.length}
                  </div>
                </div>
                <button
                  onClick={handleNextAccount}
                  className="p-2 hover:bg-muted rounded-md transition-colors disabled:opacity-50"
                  disabled={accounts.length <= 1}
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
                <button
                  onClick={handleRefresh}
                  className="p-2 hover:bg-muted rounded-md transition-colors ml-2"
                  disabled={summaryLoading}
                >
                  <RefreshCw className={`w-5 h-5 ${summaryLoading ? 'animate-spin' : ''}`} />
                </button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-6">
            {summaryLoading ? (
              <div className="text-center py-8 text-muted-foreground">Loading summary...</div>
            ) : accountSummary?.success === false ? (
              <div className="text-center py-8 text-destructive">
                {accountSummary?.error || 'Could not load summary'}
              </div>
            ) : (
              <div className="space-y-6">
                {/* Today's Stats */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg bg-muted/50 border border-border">
                    <div className="text-sm text-muted-foreground uppercase tracking-wider mb-2">
                      Today's Profit/Loss
                    </div>
                    <div className={`text-3xl font-mono font-bold flex items-center gap-2 ${
                      todayProfit >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {todayProfit >= 0 ? (
                        <TrendingUp className="w-6 h-6" />
                      ) : (
                        <TrendingDown className="w-6 h-6" />
                      )}
                      ${todayProfit >= 0 ? '+' : ''}{todayProfit.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {accountSummary?.date || 'Today'}
                    </div>
                  </div>
                  <div className="p-4 rounded-lg bg-muted/50 border border-border">
                    <div className="text-sm text-muted-foreground uppercase tracking-wider mb-2">
                      Week Total
                    </div>
                    <div className={`text-3xl font-mono font-bold flex items-center gap-2 ${
                      weekTotal >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {weekTotal >= 0 ? (
                        <TrendingUp className="w-6 h-6" />
                      ) : (
                        <TrendingDown className="w-6 h-6" />
                      )}
                      ${weekTotal >= 0 ? '+' : ''}{weekTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      This Week (Mon-Sun)
                    </div>
                  </div>
                </div>

                {/* Daily Breakdown Chart */}
                <div>
                  <div className="text-sm text-muted-foreground uppercase tracking-wider mb-4">
                    Daily Breakdown
                  </div>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis 
                        dataKey="day" 
                        stroke="hsl(var(--muted-foreground))" 
                        className="font-mono text-xs"
                      />
                      <YAxis 
                        stroke="hsl(var(--muted-foreground))" 
                        className="font-mono text-xs"
                        tickFormatter={(value) => `$${value >= 0 ? '+' : ''}${(value/1000).toFixed(0)}k`}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'hsl(var(--muted))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '0.25rem',
                        }}
                        formatter={(value) => [`$${value >= 0 ? '+' : ''}${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`, 'Profit/Loss']}
                        labelClassName="font-mono"
                      />
                      <Bar dataKey="profit" radius={[4, 4, 0, 0]}>
                        {chartData.map((entry, index) => (
                          <Cell 
                            key={`cell-${index}`}
                            fill={entry.profit >= 0 ? 'hsl(142, 76%, 36%)' : 'hsl(0, 84%, 60%)'}
                            stroke={entry.isToday ? 'hsl(var(--primary))' : 'transparent'}
                            strokeWidth={entry.isToday ? 2 : 0}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* Daily Details Table */}
                <div className="grid grid-cols-7 gap-2">
                  {chartData.map((day, index) => (
                    <div 
                      key={index}
                      className={`p-2 rounded text-center ${
                        day.isToday ? 'bg-primary/20 border border-primary' : 'bg-muted/30'
                      }`}
                    >
                      <div className="text-xs text-muted-foreground font-medium">
                        {day.day}
                      </div>
                      <div className={`text-sm font-mono font-bold ${
                        day.profit >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {day.profit >= 0 ? '+' : ''}{(day.profit / 1000).toFixed(1)}k
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

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
              Active Accounts
            </CardTitle>
            <User className="w-4 h-4 text-primary" strokeWidth={1.5} />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-mono font-bold text-primary">{accounts.length}</div>
          </CardContent>
        </Card>

        <Card className="glass-card neon-border" data-testid="stat-win-rate">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
              Today's P/L
            </CardTitle>
            {todayProfit >= 0 ? (
              <TrendingUp className="w-4 h-4 text-green-400" strokeWidth={1.5} />
            ) : (
              <TrendingDown className="w-4 h-4 text-red-400" strokeWidth={1.5} />
            )}
          </CardHeader>
          <CardContent>
            <div className={`text-3xl font-mono font-bold ${todayProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${todayProfit >= 0 ? '+' : ''}{todayProfit.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card neon-border" data-testid="stat-total-profit">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
              Week Total
            </CardTitle>
            <DollarSign className="w-4 h-4 text-primary" strokeWidth={1.5} />
          </CardHeader>
          <CardContent>
            <div className={`text-3xl font-mono font-bold ${weekTotal >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${weekTotal >= 0 ? '+' : ''}{weekTotal.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </div>
          </CardContent>
        </Card>
      </div>

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
                    <div className="text-sm font-medium">{bet.game || 'Bet Placed'}</div>
                    <div className="text-xs font-mono text-muted-foreground">
                      ${bet.wager_amount} • {bet.account ? (bet.account === 'jac075' ? 'ENANO' : bet.account === 'jac083' ? 'TIPSTER' : bet.account) : 'Unknown'}
                    </div>
                  </div>
                  <div className={`text-xs font-mono px-2 py-1 rounded-sm ${
                    bet.result === 'won' ? 'bg-green-500/20 text-green-400' :
                    bet.result === 'lost' ? 'bg-red-500/20 text-red-400' :
                    'bg-primary/20 text-primary'
                  }`}>
                    {(bet.result || bet.status || 'PENDING').toUpperCase()}
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
