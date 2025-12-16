import { useEffect, useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Plus, Trash2, Power } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function BettingRules() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    min_odds: '',
    max_odds: '',
    wager_amount: '',
    sport: '',
    enabled: true,
    auto_place: false,
  });

  useEffect(() => {
    loadRules();
  }, []);

  const loadRules = async () => {
    try {
      const response = await axios.get(`${API}/rules`);
      setRules(response.data);
    } catch (error) {
      console.error('Error loading rules:', error);
      toast.error('Failed to load betting rules');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        name: formData.name,
        min_odds: formData.min_odds ? parseFloat(formData.min_odds) : null,
        max_odds: formData.max_odds ? parseFloat(formData.max_odds) : null,
        wager_amount: parseFloat(formData.wager_amount),
        sport: formData.sport || null,
        enabled: formData.enabled,
        auto_place: formData.auto_place,
      };

      await axios.post(`${API}/rules`, payload);
      toast.success('Betting rule created successfully');
      setDialogOpen(false);
      setFormData({
        name: '',
        min_odds: '',
        max_odds: '',
        wager_amount: '',
        sport: '',
        enabled: true,
        auto_place: false,
      });
      loadRules();
    } catch (error) {
      console.error('Error creating rule:', error);
      toast.error('Failed to create rule');
    }
  };

  const handleDelete = async (ruleId) => {
    try {
      await axios.delete(`${API}/rules/${ruleId}`);
      toast.success('Rule deleted');
      loadRules();
    } catch (error) {
      console.error('Error deleting rule:', error);
      toast.error('Failed to delete rule');
    }
  };

  if (loading) {
    return <div className="text-center text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-tight mb-2" data-testid="rules-title">
            Betting Rules
          </h1>
          <p className="text-muted-foreground">Define scenarios for automated betting</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="create-rule-button" className="bg-primary text-primary-foreground hover:bg-primary/90 neon-glow">
              <Plus className="w-4 h-4 mr-2" strokeWidth={1.5} />
              New Rule
            </Button>
          </DialogTrigger>
          <DialogContent className="glass-card neon-border">
            <DialogHeader>
              <DialogTitle className="font-heading text-2xl">Create Betting Rule</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Set up a new automated betting scenario
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label htmlFor="name">Rule Name</Label>
                <Input
                  id="name"
                  data-testid="rule-name-input"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Soccer High Odds"
                  required
                  className="bg-muted border-input"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="min_odds">Min Odds</Label>
                  <Input
                    id="min_odds"
                    data-testid="min-odds-input"
                    type="number"
                    step="0.1"
                    value={formData.min_odds}
                    onChange={(e) => setFormData({ ...formData, min_odds: e.target.value })}
                    placeholder="1.5"
                    className="bg-muted border-input font-mono"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max_odds">Max Odds</Label>
                  <Input
                    id="max_odds"
                    data-testid="max-odds-input"
                    type="number"
                    step="0.1"
                    value={formData.max_odds}
                    onChange={(e) => setFormData({ ...formData, max_odds: e.target.value })}
                    placeholder="3.0"
                    className="bg-muted border-input font-mono"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="wager_amount">Wager Amount ($)</Label>
                <Input
                  id="wager_amount"
                  data-testid="wager-amount-input"
                  type="number"
                  step="0.01"
                  value={formData.wager_amount}
                  onChange={(e) => setFormData({ ...formData, wager_amount: e.target.value })}
                  placeholder="10.00"
                  required
                  className="bg-muted border-input font-mono"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="sport">Sport (Optional)</Label>
                <Input
                  id="sport"
                  data-testid="sport-input"
                  value={formData.sport}
                  onChange={(e) => setFormData({ ...formData, sport: e.target.value })}
                  placeholder="e.g., Soccer, Basketball"
                  className="bg-muted border-input"
                />
              </div>

              <div className="flex items-center justify-between py-2">
                <Label htmlFor="auto_place" className="cursor-pointer">
                  Auto-place bets
                </Label>
                <Switch
                  id="auto_place"
                  data-testid="auto-place-switch"
                  checked={formData.auto_place}
                  onCheckedChange={(checked) => setFormData({ ...formData, auto_place: checked })}
                />
              </div>

              <Button type="submit" data-testid="save-rule-button" className="w-full bg-primary text-primary-foreground hover:bg-primary/90">
                Create Rule
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {rules.length === 0 ? (
          <Card className="glass-card neon-border col-span-full">
            <CardContent className="pt-6 text-center text-muted-foreground">
              <p>No betting rules created yet. Create your first rule to get started.</p>
            </CardContent>
          </Card>
        ) : (
          rules.map((rule) => (
            <Card key={rule.id} className="glass-card neon-border" data-testid={`rule-card-${rule.id}`}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="font-heading text-lg">{rule.name}</CardTitle>
                    <CardDescription className="text-xs font-mono text-muted-foreground mt-1">
                      ID: {rule.id.substring(0, 8)}
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      data-testid={`delete-rule-${rule.id}`}
                      onClick={() => handleDelete(rule.id)}
                      className="h-8 w-8 p-0 hover:bg-destructive/20 hover:text-destructive"
                    >
                      <Trash2 className="w-4 h-4" strokeWidth={1.5} />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  {rule.min_odds && (
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Min Odds:</span>
                      <span className="font-mono text-foreground">{rule.min_odds}</span>
                    </div>
                  )}
                  {rule.max_odds && (
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Max Odds:</span>
                      <span className="font-mono text-foreground">{rule.max_odds}</span>
                    </div>
                  )}
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Wager:</span>
                    <span className="font-mono text-primary">${rule.wager_amount}</span>
                  </div>
                  {rule.sport && (
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Sport:</span>
                      <span className="font-mono text-foreground">{rule.sport}</span>
                    </div>
                  )}
                </div>

                <div className="pt-3 border-t border-border flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Power className={`w-3 h-3 ${rule.enabled ? 'text-primary' : 'text-muted-foreground'}`} strokeWidth={1.5} />
                    <span className="text-xs uppercase tracking-wider font-mono text-muted-foreground">
                      {rule.enabled ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                  </div>
                  {rule.auto_place && (
                    <span className="text-xs px-2 py-1 rounded-sm bg-primary/20 text-primary font-mono">
                      AUTO
                    </span>
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
