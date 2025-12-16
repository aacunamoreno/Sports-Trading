import { useEffect, useState } from 'react';
import axios from 'axios';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Clock } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function History() {
  const [bets, setBets] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const response = await axios.get(`${API}/bets/history`);
      setBets(response.data);
    } catch (error) {
      console.error('Error loading history:', error);
      toast.error('Failed to load bet history');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleString();
    } catch {
      return dateStr;
    }
  };

  if (loading) {
    return <div className="text-center text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-4xl font-heading font-bold tracking-tight mb-2" data-testid="history-title">
          Bet History
        </h1>
        <p className="text-muted-foreground">Track all your placed bets and results</p>
      </div>

      <Card className="glass-card neon-border">
        <CardContent className="p-0">
          {bets.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" strokeWidth={1.5} />
              <p>No betting history yet.</p>
              <p className="text-sm mt-2">Your placed bets will appear here.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-b border-border hover:bg-transparent">
                  <TableHead className="font-mono uppercase tracking-wider text-xs">Date</TableHead>
                  <TableHead className="font-mono uppercase tracking-wider text-xs">ID</TableHead>
                  <TableHead className="font-mono uppercase tracking-wider text-xs">Wager</TableHead>
                  <TableHead className="font-mono uppercase tracking-wider text-xs">Odds</TableHead>
                  <TableHead className="font-mono uppercase tracking-wider text-xs">Status</TableHead>
                  <TableHead className="font-mono uppercase tracking-wider text-xs text-right">Result</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {bets.map((bet) => (
                  <TableRow
                    key={bet.id}
                    data-testid={`bet-row-${bet.id}`}
                    className="border-b border-border/50 hover:bg-white/5 transition-colors duration-200"
                  >
                    <TableCell className="font-mono text-sm text-muted-foreground">
                      {formatDate(bet.placed_at)}
                    </TableCell>
                    <TableCell className="font-mono text-sm">{bet.id.substring(0, 8)}</TableCell>
                    <TableCell className="font-mono text-sm text-primary">${bet.wager_amount}</TableCell>
                    <TableCell className="font-mono text-sm">{bet.odds || '-'}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-block px-2 py-1 rounded-sm text-xs font-mono uppercase tracking-wider ${
                          bet.status === 'placed'
                            ? 'bg-primary/20 text-primary'
                            : bet.status === 'won'
                            ? 'bg-green-500/20 text-green-400'
                            : bet.status === 'lost'
                            ? 'bg-destructive/20 text-destructive'
                            : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {bet.status}
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-sm text-right">
                      {bet.result || '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
