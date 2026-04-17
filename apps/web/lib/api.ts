import axios from "axios";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const WS_BASE_URL = BASE_URL.replace(/^http/, "ws");

const api = axios.create({ baseURL: BASE_URL });

export interface MarketTick {
  type: "tick" | "ping";
  symbol?: string;
  price?: number;
  bid?: number;
  ask?: number;
  asset_class?: string;
  timestamp?: string;
}

export interface BotStatus {
  status: string;
  started_at: string | null;
  last_scan_at: string | null;
  last_signal_at: string | null;
  trades_today: number;
  errors_today: number;
  last_error: string | null;
}

export interface BotSummary {
  status: string;
  trades_today: number;
  errors_today: number;
  last_scan_at: string | null;
  last_signal_at: string | null;
  equity: number | null;
}

export interface AlpacaAccount {
  equity: string;
  cash: string;
  portfolio_value: string;
  buying_power: string;
  [key: string]: unknown;
}

export interface ScanResult {
  symbol: string;
  asset_class: string;
  fired_timeframes: string[];
  aggregate_score: number;
  should_trade: boolean;
  suggested_side: string;
}

export interface WatchlistScanResult {
  scanned_at: string;
  results: ScanResult[];
  top_pick: ScanResult | null;
}

export interface Position {
  symbol: string;
  qty: string;
  avg_entry_price: string;
  current_price: string;
  unrealized_pl: string;
  side: string;
  [key: string]: unknown;
}

export interface Order {
  id: string;
  symbol: string;
  side: string;
  qty: string;
  filled_avg_price: string | null;
  status: string;
  created_at: string;
  [key: string]: unknown;
}

export interface BotOrder {
  id: number;
  symbol: string;
  side: string;
  quantity: number;
  fill_price: number;
  status: string;
  created_at: string;
}

export interface PortfolioHistory {
  timestamp: number[];
  equity: number[];
  profit_loss: number[];
  profit_loss_pct: number[];
  base_value: number;
  timeframe: string;
}

export async function getAccount(): Promise<AlpacaAccount> {
  const res = await api.get("/broker/account");
  return res.data;
}

export async function getBotStatus(): Promise<BotStatus> {
  const res = await api.get("/bot/status");
  return res.data;
}

export async function getBotSummary(): Promise<BotSummary> {
  const res = await api.get("/bot/summary");
  return res.data;
}

export async function startBot(): Promise<void> {
  await api.post("/bot/start");
}

export async function stopBot(): Promise<void> {
  await api.post("/bot/stop");
}

export async function pauseBot(): Promise<void> {
  await api.post("/bot/pause");
}

export async function getWatchlistScan(): Promise<WatchlistScanResult> {
  const res = await api.get("/scanner/watchlist");
  return res.data;
}

export async function getPositions(): Promise<Position[]> {
  const res = await api.get("/broker/positions");
  return res.data;
}

export async function getOrders(status = "open"): Promise<Order[]> {
  const res = await api.get("/broker/orders", { params: { status } });
  return res.data;
}

export async function getBotHistory(limit = 50): Promise<BotOrder[]> {
  const res = await api.get("/bot/history", { params: { limit } });
  return res.data;
}

export async function getPortfolioHistory(): Promise<PortfolioHistory> {
  const res = await api.get("/broker/portfolio/history");
  return res.data;
}

export async function setKillSwitch(enabled: boolean): Promise<void> {
  await api.post("/risk/kill-switch/global", { enabled });
}

export interface TradeJournalEntry {
  id: number;
  symbol: string;
  asset_class: string;
  side: string;
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  stop_loss_price: number;
  take_profit_price: number;
  entry_signal_rules: string[];
  realized_pnl: number | null;
  status: string;
  opened_at: string;
  closed_at: string | null;
}

export interface Performance {
  win_rate: number;
  sharpe: number;
  max_drawdown: number;
  avg_win: number;
  avg_loss: number;
  ratio: number;
  total_trades: number;
  open_trades: number;
}

export interface PnlPoint {
  date: string;
  pnl: number;
  cumulative_pnl: number;
}

export async function getPerformance(): Promise<Performance> {
  const res = await api.get("/analytics/performance");
  return res.data;
}

export async function getTrades(status?: string, limit = 100): Promise<TradeJournalEntry[]> {
  const res = await api.get("/analytics/trades", { params: { status, limit } });
  return res.data;
}

export async function getPnlSeries(): Promise<PnlPoint[]> {
  const res = await api.get("/analytics/pnl-series");
  return res.data;
}

// ---------------------------------------------------------------------------
// Backtest
// ---------------------------------------------------------------------------

export interface BacktestTrade {
  entry_date: string;
  exit_date: string | null;
  entry_price: number;
  exit_price: number | null;
  side: string;
  quantity: number;
  stop_loss_price: number;
  take_profit_price: number;
  realized_pnl: number | null;
  status: string;
  fired_rules: string[];
}

export interface BacktestMetrics {
  total_trades: number;
  win_rate: number;
  sharpe: number;
  max_drawdown: number;
  avg_win: number;
  avg_loss: number;
  ratio: number;
  total_pnl: number;
  starting_equity: number;
  ending_equity: number;
}

export interface BacktestResult {
  symbol: string;
  asset_class: string;
  start: string;
  end: string;
  timeframe: string;
  total_bars: number;
  trades: BacktestTrade[];
  metrics: BacktestMetrics;
  equity_curve: number[];
}

export interface BacktestRequest {
  symbol: string;
  asset_class?: string;
  start: string;
  end: string;
  timeframe?: string;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  starting_equity?: number;
  position_size_pct?: number;
  min_signal_score?: number;
}

export async function runBacktest(req: BacktestRequest): Promise<BacktestResult> {
  const res = await api.post("/backtest/run", req);
  return res.data;
}

export async function getBacktestSymbols(): Promise<{ stocks: string[]; crypto: string[]; all: string[] }> {
  const res = await api.get("/backtest/symbols");
  return res.data;
}

// ---------------------------------------------------------------------------
// Watchlist
// ---------------------------------------------------------------------------

export interface WatchlistEntry {
  id: number;
  symbol: string;
  asset_class: string;
  is_active: boolean;
  added_at: string;
}

export async function getWatchlist(): Promise<WatchlistEntry[]> {
  const res = await api.get("/watchlist");
  return res.data;
}

export async function addWatchlistSymbol(symbol: string, asset_class: string): Promise<WatchlistEntry> {
  const res = await api.post("/watchlist", { symbol, asset_class });
  return res.data;
}

export async function removeWatchlistSymbol(symbol: string): Promise<void> {
  await api.delete(`/watchlist/${symbol}`);
}

// ---------------------------------------------------------------------------
// App config
// ---------------------------------------------------------------------------

export async function getAppConfig(): Promise<{ demo_mode: boolean }> {
  const res = await api.get("/health/config");
  return res.data;
}
