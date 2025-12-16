import { useEffect, useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw, Target, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Opportunities() {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    loadOpportunities();
  }, []);

  const loadOpportunities = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/opportunities`);
      setOpportunities(response.data.opportunities || []);
      if (response.data.message) {
        setMessage(response.data.message);
      }
    } catch (error) {
      console.error('Error loading opportunities:', error);
      toast.error('Failed to load opportunities');
    } finally {
      setLoading(false);
    }
  };

  const handlePlaceBet = async (opportunity) => {
    try {
      await axios.post(`${API}/bets/place`, {
        opportunity_id: opportunity.id,
        wager_amount: opportunity.wager_amount,
      });
      toast.success(`Bet placed: $${opportunity.wager_amount} on ${opportunity.event_name}`);
      loadOpportunities();
    } catch (error) {
      console.error('Error placing bet:', error);
      toast.error('Failed to place bet');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-tight mb-2" data-testid="opportunities-title">
            Live Opportunities
          </h1>
          <p className="text-muted-foreground">Betting opportunities matching your rules</p>
        </div>
        <Button
          onClick={loadOpportunities}
          disabled={loading}
          data-testid="refresh-opportunities-button"
          className="bg-primary text-primary-foreground hover:bg-primary/90 neon-glow"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} strokeWidth={1.5} />
          Refresh
        </Button>
      </div>

      {message && (
        <Card className="glass-card border-primary/30" data-testid="info-message">
          <CardContent className="pt-6">
            <p className="text-center text-muted-foreground">{message}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {opportunities.length === 0 && !message ? (
          <Card className="glass-card neon-border col-span-full">
            <CardContent className="pt-6 text-center text-muted-foreground">
              <Target className="w-12 h-12 mx-auto mb-4 opacity-50" strokeWidth={1.5} />
              <p>No opportunities found matching your rules.</p>
              <p className="text-sm mt-2">Try adjusting your betting rules or check back later.</p>
            </CardContent>
          </Card>
        ) : (
          opportunities.map((opp) => (
            <Card key={opp.id} className="glass-card neon-border" data-testid={`opportunity-card-${opp.id}`}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <CardTitle className="font-heading text-lg">{opp.event_name}</CardTitle>
                    <CardDescription className="text-xs font-mono text-muted-foreground mt-1">
                      {opp.sport} • {opp.bet_type}
                    </CardDescription>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-mono font-bold text-primary">{opp.odds}</div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider">ODDS</div>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Matched Rule:</span>
                    <span className="font-mono text-foreground">{opp.matched_rule_name}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Wager Amount:</span>
                    <span className="font-mono text-primary">${opp.wager_amount}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Potential Win:</span>
                    <span className="font-mono text-green-400">
                      ${(opp.wager_amount * opp.odds).toFixed(2)}
                    </span>
                  </div>
                </div>

                <div className="pt-3 border-t border-border">
                  {opp.auto_place ? (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground justify-center">
                      <TrendingUp className="w-3 h-3" strokeWidth={1.5} />
                      <span>Will be placed automatically</span>
                    </div>
                  ) : (
                    <Button
                      onClick={() => handlePlaceBet(opp)}
                      data-testid={`place-bet-${opp.id}`}
                      className="w-full bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-200"
                    >
                      Place Bet
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
