import axios from "axios";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: BASE_URL });

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
