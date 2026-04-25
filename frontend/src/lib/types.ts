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
  flow_recent: number[];
  margin_trend_note: string;
  notes: string[];
  alerts: Alert[];
}

export interface FundamentalReport {
  code: string;
  name: string;
  overall: 'STRONG' | 'HEALTHY' | 'CAUTION' | 'RISKY';
  pass_count: number;
  warn_count: number;
  fail_count: number;
  metrics: FundamentalMetric[];
}

export interface FundamentalMetric {
  name: string;
  score: 'PASS' | 'WARN' | 'FAIL' | 'N/A';
  value: number | null;
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
