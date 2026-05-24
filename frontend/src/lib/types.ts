export interface PriceBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface FlowRow {
  date: string;
  foreign_net: number | null;
  institution_net: number | null;
  individual_net: number | null;
}

export interface MarginRow {
  week: string;
  margin_long: number;
  margin_short: number;
  ratio: number;
}

export interface EdinetEvent {
  date: string;
  filer: string;
  doc_type: string;
  pdf_url: string;
}

export interface SignalConditions {
  cond_inst_sell: boolean;
  cond_margin_surge: boolean;
  cond_price_rise: boolean;
  matched: number;
}

export interface Alert {
  alert_type: 'exit' | 'stop_loss' | 'accumulation' | 'info';
  severity: 'info' | 'warn' | 'critical';
  message: string;
  details: Record<string, unknown>;
}

export interface SignalResult {
  code: string;
  name: string;
  latest_price: number | null;
  latest_date: string | null;
  start_price: number | null;
  price_vs_start_pct: number | null;
  price_vs_recent_low_pct: number | null;
  conditions: SignalConditions;
  stop_loss_triggered: boolean;
  accumulation_signal: boolean;
  trailing_stop_stage: number | null;
  trailing_stop_price: number | null;
  trailing_stop_triggered: boolean;
  trailing_stop_anchor: string | null;
  atr_14: number | null;
  exit_warnings: string[];
  flow_recent: number[];
  margin_trend_note: string;
  notes: string[];
  alerts: Alert[];
  indicator_signals?: unknown[];
  technical_score?: number;
}

export interface FundamentalReport {
  code: string;
  name: string;
  overall: 'STRONG' | 'HEALTHY' | 'CAUTION' | 'RISKY';
  metrics: FundamentalMetric[];
}

export interface FundamentalMetric {
  metric: string;
  score: 'PASS' | 'WARN' | 'FAIL' | 'N/A';
  note: string;
}

export interface DpsRow {
  fiscal_year: number;
  dps: number;
  eps: number;
}

export interface FavoriteEntry {
  code: string;
  name: string;
  tags: string[];
  added_at: string;
  note: string;
}

export interface SignalScanRow {
  code: string;
  name: string;
  latest_price: number;
  has_accumulation: boolean;
  has_exit: boolean;
  has_stop_loss: boolean;
  edinet_recent_count: number;
  score: number;
  generated_at: string;
}

export interface DividendScanRow {
  code: string;
  name: string;
  overall: string;
  pass_count: number;
  warn_count: number;
  fail_count: number;
  latest_dps: number;
  dps_streak_no_cut: number;
  est_yield: number;
  payout_avg: number;
  equity_ratio_latest: number;
  eps_growth: number;
  generated_at: string;
}

export interface WatchlistEntry {
  code: string;
  name: string;
  start_price: number;
}

export interface PortfolioLot {
  id: string;
  code: string;
  name: string;
  entry_price: number;
  quantity: number;
  entry_date: string;
  exit_price: number | null;
  exit_date: string | null;
  note: string;
  current_price: number | null;
  unrealized_pnl: number | null;
  return_pct: number | null;
}

export interface PortfolioEntry {
  code: string;
  name: string;
  lots: PortfolioLot[];
  total_cost: number;
  total_unrealized_pnl: number | null;
}

// Simulation types
export interface CandidateEntry {
  code: string;
  name: string;
  entry_signal_date: string | null;
  forced_entry_date: string | null;
}

export type IndicatorConditionType =
  | 'rsi_oversold' | 'rsi_overbought'
  | 'macd_golden_cross' | 'macd_dead_cross'
  | 'sma_cross' | 'bb_breakout_up' | 'bb_breakout_down';

export interface IndicatorCondition {
  type: IndicatorConditionType;
  params: Record<string, unknown>;
}

export interface EntryRule {
  price_basis: 'signal_close' | 'next_open' | 'user_specified';
  user_price: number | null;
  require_signal: boolean;
  indicator_entry: IndicatorCondition[];
  indicator_entry_logic: 'and' | 'or';
}

export interface ExitRule {
  use_exit_signal: boolean;
  use_stop_loss: boolean;
  stop_loss_pct: number | null;
  take_profit_pct: number | null;
  max_hold_days: number | null;
  exit_price_basis: 'signal_close' | 'next_open';
  indicator_exit: IndicatorCondition[];
  indicator_exit_logic: 'and' | 'or';
}

export interface PositionSizing {
  mode: 'equal_weight' | 'fixed_jpy' | 'fixed_shares';
  fixed_jpy: number | null;
  fixed_shares: number | null;
  max_concurrent_positions: number;
}

export interface CostModel {
  commission_pct: number;
  slippage_pct: number;
  tax_pct: number;
}

export interface SimulationConfig {
  kind: 'backtest' | 'paper';
  initial_capital: number;
  start_date: string;
  end_date: string | null;
  candidates: CandidateEntry[];
  entry_rule: EntryRule;
  exit_rule: ExitRule;
  position_sizing: PositionSizing;
  cost_model: CostModel;
}

export interface Position {
  code: string;
  name: string;
  entry_date: string;
  entry_price: number;
  shares: number;
  cost_basis: number;
}

export interface ClosedTrade {
  code: string;
  name: string;
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  shares: number;
  pnl_jpy: number;
  pnl_pct: number;
  hold_days: number;
  exit_reason: 'exit_signal' | 'stop_loss' | 'take_profit' | 'max_hold' | 'end_of_sim' | 'manual' | 'indicator_exit';
}

export interface EquityPoint {
  date: string;
  cash: number;
  market_value: number;
  equity: number;
}

export interface SimulationState {
  cash: number;
  positions: Position[];
  closed_trades: ClosedTrade[];
  equity_curve: EquityPoint[];
  cursor_date: string;
  pending_entries: CandidateEntry[];
}

export interface Simulation {
  id: string;
  name: string;
  created_at: string;
  config: SimulationConfig;
  state: SimulationState;
  status: 'draft' | 'running' | 'completed' | 'failed';
}

export interface SimulationReport {
  id: string;
  name: string;
  kind: 'backtest' | 'paper';
  status: 'draft' | 'running' | 'completed' | 'failed';
  period_start: string;
  period_end: string;
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  annualized_return_pct: number;
  max_drawdown_pct: number;
  win_rate: number;
  avg_pnl_pct: number;
  avg_hold_days: number;
  profit_factor: number;
  total_trades: number;
  closed_trades: ClosedTrade[];
  equity_curve: EquityPoint[];
  exit_reason_breakdown: Record<string, number>;
  strategy_type: 'pure_signal' | 'signal_indicator' | 'pure_indicator';
}
