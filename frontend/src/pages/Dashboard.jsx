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

  const loadAccountSummary = useCallback(async (username, forceRefresh = false) => {
    // Use cached summary if available and not forcing refresh
    if (!forceRefresh && allSummaries[username]) {
      setAccountSummary(allSummaries[username]);
      return;
    }
    
    setSummaryLoading(true);
    try {
      const response = await axios.get(`${API}/accounts/${username}/summary?force_refresh=${forceRefresh}`);
      setAccountSummary(response.data);
      // Update cache
      setAllSummaries(prev => ({...prev, [username]: response.data}));
    } catch (error) {
      console.error('Error loading account summary:', error);
      setAccountSummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }, [allSummaries]);

  const handlePrevAccount = () => {
    const newIndex = selectedAccountIndex > 0 ? selectedAccountIndex - 1 : accounts.length - 1;
    setSelectedAccountIndex(newIndex);
    if (accounts[newIndex]) {
      loadAccountSummary(accounts[newIndex].username, false);
    }
  };

  const handleNextAccount = () => {
    const newIndex = selectedAccountIndex < accounts.length - 1 ? selectedAccountIndex + 1 : 0;
    setSelectedAccountIndex(newIndex);
    if (accounts[newIndex]) {
      loadAccountSummary(accounts[newIndex].username, false);
    }
  };

  const handleRefresh = () => {
    if (accounts[selectedAccountIndex]) {
      loadAccountSummary(accounts[selectedAccountIndex].username, true);
    }
  };

  // Day display names and order
  const dayDisplayNames = {
    'mon': 'Mon', 'tue': 'Tue', 'wed': 'Wed',
    'thu': 'Thu', 'fri': 'Fri', 'sat': 'Sat', 'sun': 'Sun'
  };
  const dayOrder = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

  // Get today's index for determining future days
  const todayIndex = accountSummary?.today_day ? dayOrder.indexOf(accountSummary.today_day) : -1;

  // Prepare chart data from account summary
  const chartData = accountSummary?.daily_profits?.map((d, idx) => {
    const dayIdx = dayOrder.indexOf(d.day);
    return {
      day: dayDisplayNames[d.day] || d.day,
      profit: d.profit,
      isToday: d.day === accountSummary?.today_day,
      isFuture: todayIndex >= 0 && dayIdx > todayIndex
    };
  }) || [
    { day: 'Mon', profit: 0, isFuture: false },
    { day: 'Tue', profit: 0, isFuture: false },
    { day: 'Wed', profit: 0, isFuture: false },
    { day: 'Thu', profit: 0, isFuture: false },
    { day: 'Fri', profit: 0, isFuture: true },
    { day: 'Sat', profit: 0, isFuture: true },
    { day: 'Sun', profit: 0, isFuture: true },
  ];

  if (loading) {
    return <div className="text-center text-muted-foreground py-12">Loading...</div>;
  }

  const currentAccount = accounts[selectedAccountIndex];
  const todayProfit = accountSummary?.today_profit || 0;
  const weekTotal = accountSummary?.week_total || 0;

  return (
    <div className="space-y-4 lg:space-y-6">
      {/* Header - Responsive */}
      <div>
        <h1 className="text-2xl lg:text-4xl font-heading font-bold tracking-tight mb-1 lg:mb-2" data-testid="dashboard-title">
          Control Room
        </h1>
        <p className="text-sm lg:text-base text-muted-foreground">Monitor your automated betting operations</p>
      </div>

      {/* Account Selector Card */}
      {accounts.length > 0 && (
        <Card className="glass-card neon-border">
          <CardHeader className="border-b border-border pb-3 lg:pb-4 px-3 lg:px-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="flex items-center gap-2 lg:gap-3">
                <User className="w-4 h-4 lg:w-5 lg:h-5 text-primary" />
                <CardTitle className="font-heading text-base lg:text-lg">Account Summary</CardTitle>
              </div>
              <div className="flex items-center justify-between sm:justify-end gap-2">
                <button
                  onClick={handlePrevAccount}
                  className="p-1.5 lg:p-2 hover:bg-muted rounded-md transition-colors disabled:opacity-50"
                  disabled={accounts.length <= 1}
                >
                  <ChevronLeft className="w-4 h-4 lg:w-5 lg:h-5" />
                </button>
                <div className="min-w-[100px] lg:min-w-[120px] text-center">
                  <span className="font-mono font-bold text-primary text-base lg:text-lg">
                    {currentAccount?.label || 'No Account'}
                  </span>
                  <div className="text-xs text-muted-foreground">
                    {selectedAccountIndex + 1} of {accounts.length}
                  </div>
                </div>
                <button
                  onClick={handleNextAccount}
                  className="p-1.5 lg:p-2 hover:bg-muted rounded-md transition-colors disabled:opacity-50"
                  disabled={accounts.length <= 1}
                >
                  <ChevronRight className="w-4 h-4 lg:w-5 lg:h-5" />
                </button>
                <button
                  onClick={handleRefresh}
                  className="p-1.5 lg:p-2 hover:bg-muted rounded-md transition-colors ml-1 lg:ml-2"
                  disabled={summaryLoading}
                >
                  <RefreshCw className={`w-4 h-4 lg:w-5 lg:h-5 ${summaryLoading ? 'animate-spin' : ''}`} />
                </button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-4 lg:pt-6 px-3 lg:px-6">
            {summaryLoading ? (
              <div className="text-center py-6 lg:py-8 text-muted-foreground">Loading summary...</div>
            ) : accountSummary?.success === false ? (
              <div className="text-center py-6 lg:py-8 text-destructive text-sm">
                {accountSummary?.error || 'Could not load summary'}
              </div>
            ) : (
              <div className="space-y-4 lg:space-y-6">
                {/* Today's Stats - Responsive Grid */}
                <div className="grid grid-cols-2 gap-3 lg:gap-4">
                  <div className="p-3 lg:p-4 rounded-lg bg-muted/50 border border-border">
                    <div className="text-xs lg:text-sm text-muted-foreground uppercase tracking-wider mb-1 lg:mb-2">
                      Today's P/L
                    </div>
                    <div className={`text-xl lg:text-3xl font-mono font-bold flex items-center gap-1 lg:gap-2 ${
                      todayProfit >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {todayProfit >= 0 ? (
                        <TrendingUp className="w-4 h-4 lg:w-6 lg:h-6 flex-shrink-0" />
                      ) : (
                        <TrendingDown className="w-4 h-4 lg:w-6 lg:h-6 flex-shrink-0" />
                      )}
                      <span className="truncate">
                        ${todayProfit >= 0 ? '+' : ''}{todayProfit.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {accountSummary?.date || 'Today'}
                    </div>
                  </div>
                  <div className="p-3 lg:p-4 rounded-lg bg-muted/50 border border-border">
                    <div className="text-xs lg:text-sm text-muted-foreground uppercase tracking-wider mb-1 lg:mb-2">
                      Week Total
                    </div>
                    <div className={`text-xl lg:text-3xl font-mono font-bold flex items-center gap-1 lg:gap-2 ${
                      weekTotal >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {weekTotal >= 0 ? (
                        <TrendingUp className="w-4 h-4 lg:w-6 lg:h-6 flex-shrink-0" />
                      ) : (
                        <TrendingDown className="w-4 h-4 lg:w-6 lg:h-6 flex-shrink-0" />
                      )}
                      <span className="truncate">
                        ${weekTotal >= 0 ? '+' : ''}{weekTotal.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Mon-Sun
                    </div>
                  </div>
                </div>

                {/* Daily Breakdown Chart */}
                <div>
                  <div className="text-xs lg:text-sm text-muted-foreground uppercase tracking-wider mb-3 lg:mb-4">
                    Daily Breakdown
                  </div>
                  <ResponsiveContainer width="100%" height={160}>
                    <BarChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis 
                        dataKey="day" 
                        stroke="hsl(var(--muted-foreground))" 
                        tick={{ fontSize: 10 }}
                      />
                      <YAxis 
                        stroke="hsl(var(--muted-foreground))" 
                        tick={{ fontSize: 10 }}
                        tickFormatter={(value) => `${(value/1000).toFixed(0)}k`}
                        width={40}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'hsl(var(--muted))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '0.25rem',
                          fontSize: '12px',
                        }}
                        formatter={(value) => [`$${value >= 0 ? '+' : ''}${value.toLocaleString('en-US', { minimumFractionDigits: 0 })}`, 'P/L']}
                      />
                      <Bar dataKey="profit" radius={[4, 4, 0, 0]}>
                        {chartData.map((entry, index) => (
                          <Cell 
                            key={`cell-${index}`}
                            fill={entry.isFuture ? 'hsl(199, 89%, 48%)' : entry.profit >= 0 ? 'hsl(142, 76%, 36%)' : 'hsl(0, 84%, 60%)'}
                            stroke={entry.isToday ? 'hsl(var(--primary))' : 'transparent'}
                            strokeWidth={entry.isToday ? 2 : 0}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* Daily Details - Scrollable on mobile */}
                <div className="overflow-x-auto -mx-3 px-3 lg:mx-0 lg:px-0">
                  <div className="grid grid-cols-7 gap-1 lg:gap-2 min-w-[320px]">
                    {chartData.map((day, index) => (
                      <div 
                        key={index}
                        className={`p-1.5 lg:p-2 rounded text-center ${
                          day.isToday ? 'bg-primary/20 border border-primary' : 'bg-muted/30'
                        }`}
                      >
                        <div className="text-[10px] lg:text-xs text-muted-foreground font-medium">
                          {day.day}
                        </div>
                        <div className={`text-xs lg:text-sm font-mono font-bold ${
                          day.isFuture ? 'text-sky-400' : day.profit >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {day.profit >= 0 ? '+' : ''}{(day.profit / 1000).toFixed(1)}k
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Stats Grid - 2x2 on mobile, 4 cols on desktop */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-4">
        <Card className="glass-card neon-border" data-testid="stat-total-bets">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1 lg:pb-2 px-3 lg:px-6 pt-3 lg:pt-6">
            <CardTitle className="text-xs lg:text-sm font-medium uppercase tracking-wider text-muted-foreground">
              {currentAccount?.label || 'Account'} Bets
            </CardTitle>
            <Activity className="w-3 h-3 lg:w-4 lg:h-4 text-primary" strokeWidth={1.5} />
          </CardHeader>
          <CardContent className="px-3 lg:px-6 pb-3 lg:pb-6">
            <div className="text-2xl lg:text-3xl font-mono font-bold text-primary">{accountSummary?.total_bets !== undefined ? accountSummary.total_bets : 0}</div>
          </CardContent>
        </Card>

        <Card className="glass-card neon-border" data-testid="stat-active-rules">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1 lg:pb-2 px-3 lg:px-6 pt-3 lg:pt-6">
            <CardTitle className="text-xs lg:text-sm font-medium uppercase tracking-wider text-muted-foreground">
              Accounts
            </CardTitle>
            <User className="w-3 h-3 lg:w-4 lg:h-4 text-primary" strokeWidth={1.5} />
          </CardHeader>
          <CardContent className="px-3 lg:px-6 pb-3 lg:pb-6">
            <div className="text-2xl lg:text-3xl font-mono font-bold text-primary">{accounts.length}</div>
          </CardContent>
        </Card>

        <Card className="glass-card neon-border" data-testid="stat-win-rate">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1 lg:pb-2 px-3 lg:px-6 pt-3 lg:pt-6">
            <CardTitle className="text-xs lg:text-sm font-medium uppercase tracking-wider text-muted-foreground">
              Today P/L
            </CardTitle>
            {todayProfit >= 0 ? (
              <TrendingUp className="w-3 h-3 lg:w-4 lg:h-4 text-green-400" strokeWidth={1.5} />
            ) : (
              <TrendingDown className="w-3 h-3 lg:w-4 lg:h-4 text-red-400" strokeWidth={1.5} />
            )}
          </CardHeader>
          <CardContent className="px-3 lg:px-6 pb-3 lg:pb-6">
            <div className={`text-xl lg:text-3xl font-mono font-bold ${todayProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${todayProfit >= 0 ? '+' : ''}{(todayProfit/1000).toFixed(1)}k
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card neon-border" data-testid="stat-total-profit">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1 lg:pb-2 px-3 lg:px-6 pt-3 lg:pt-6">
            <CardTitle className="text-xs lg:text-sm font-medium uppercase tracking-wider text-muted-foreground">
              Week Total
            </CardTitle>
            <DollarSign className="w-3 h-3 lg:w-4 lg:h-4 text-primary" strokeWidth={1.5} />
          </CardHeader>
          <CardContent className="px-3 lg:px-6 pb-3 lg:pb-6">
            <div className={`text-xl lg:text-3xl font-mono font-bold ${weekTotal >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${weekTotal >= 0 ? '+' : ''}{(weekTotal/1000).toFixed(1)}k
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Activity Log */}
      <Card className="glass-card neon-border" data-testid="activity-log">
        <CardHeader className="border-b border-border px-3 lg:px-6 py-3 lg:py-4">
          <CardTitle className="font-heading text-base lg:text-lg">Recent Activity</CardTitle>
        </CardHeader>
        <CardContent className="pt-3 lg:pt-4 px-3 lg:px-6">
          <div className="space-y-2 lg:space-y-3">
            {recentBets.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-6 lg:py-8">No recent activity</p>
            ) : (
              recentBets.map((bet) => (
                <div key={bet.id} className="flex items-center justify-between py-2 border-b border-border/50">
                  <div className="min-w-0 flex-1 pr-2">
                    <div className="text-xs lg:text-sm font-medium truncate">{bet.game || 'Bet Placed'}</div>
                    <div className="text-xs font-mono text-muted-foreground">
                      ${bet.wager_amount} • {bet.account ? (bet.account === 'jac075' ? 'ENANO' : bet.account === 'jac083' ? 'TIPSTER' : bet.account) : 'Unknown'}
                    </div>
                  </div>
                  <div className={`text-xs font-mono px-2 py-1 rounded-sm flex-shrink-0 ${
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
