"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  Activity,
  Play,
  Pause,
  Square,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Minus,
  Wifi,
  WifiOff,
  Plus,
  X,
  Bitcoin,
  BarChart2,
  Shield,
  Zap,
} from "lucide-react";
import {
  getBotSummary,
  getWatchlistScan,
  getPositions,
  getBotHistory,
  getPortfolioHistory,
  getPerformance,
  getTrades,
  getBacktestSymbols,
  runBacktest,
  startBot,
  stopBot,
  pauseBot,
  setKillSwitch,
  getWatchlist,
  addWatchlistSymbol,
  removeWatchlistSymbol,
  getAppConfig,
  WS_BASE_URL,
  type BotSummary,
  type WatchlistScanResult,
  type Position,
  type BotOrder,
  type PortfolioHistory,
  type Performance,
  type TradeJournalEntry,
  type MarketTick,
  type BacktestResult,
  type WatchlistEntry,
} from "@/lib/api";

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    RUNNING: "bg-green-500",
    PAUSED: "bg-yellow-500",
    STOPPED: "bg-gray-500",
    ERROR: "bg-red-500",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-bold ${colors[status] ?? "bg-gray-600"}`}
    >
      <span className="w-2 h-2 rounded-full bg-white/70 inline-block" />
      {status}
    </span>
  );
}

function MetricCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number | null;
  sub?: string;
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4">
      <div className="text-gray-400 text-xs mb-1">{label}</div>
      <div className="text-xl font-bold text-white">
        {value ?? <span className="text-gray-600">—</span>}
      </div>
      {sub && <div className="text-gray-500 text-xs mt-1">{sub}</div>}
    </div>
  );
}

function SideIcon({ side }: { side: string }) {
  if (side === "buy") return <TrendingUp className="inline w-4 h-4 text-green-400" />;
  if (side === "sell") return <TrendingDown className="inline w-4 h-4 text-red-400" />;
  return <Minus className="inline w-4 h-4 text-gray-400" />;
}

interface Toast {
  id: number;
  msg: string;
  type: "info" | "success" | "error";
}

function ToastContainer({ toasts }: { toasts: Toast[] }) {
  if (!toasts.length) return null;
  return (
    <div className="fixed bottom-4 right-4 flex flex-col gap-2 z-50">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`px-4 py-2 rounded text-xs font-bold shadow-lg border ${
            t.type === "success"
              ? "bg-green-900 border-green-700 text-green-200"
              : t.type === "error"
                ? "bg-red-900 border-red-700 text-red-200"
                : "bg-gray-800 border-gray-700 text-gray-200"
          }`}
        >
          {t.msg}
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [summary, setSummary] = useState<BotSummary | null>(null);
  const [scan, setScan] = useState<WatchlistScanResult | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [history, setHistory] = useState<BotOrder[]>([]);
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [trades, setTrades] = useState<TradeJournalEntry[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioHistory | null>(null);
  const [killSwitch, setKillSwitchState] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [livePrices, setLivePrices] = useState<Record<string, number>>({});
  const [wsConnected, setWsConnected] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastIdRef = useRef(0);
  const wsRef = useRef<WebSocket | null>(null);
  const prevTradeIdsRef = useRef<Set<number>>(new Set());

  const [btSymbols, setBtSymbols] = useState<string[]>([]);
  const [btSymbol, setBtSymbol] = useState("AAPL");
  const [btStart, setBtStart] = useState("2024-01-01");
  const [btEnd, setBtEnd] = useState("2024-12-31");
  const [btSlPct, setBtSlPct] = useState(1.0);
  const [btTpPct, setBtTpPct] = useState(2.0);
  const [btResult, setBtResult] = useState<BacktestResult | null>(null);
  const [btLoading, setBtLoading] = useState(false);
  const [btError, setBtError] = useState<string | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [demoMode, setDemoMode] = useState(false);
  const [newSymbol, setNewSymbol] = useState("");
  const [newSymbolClass, setNewSymbolClass] = useState<"stock" | "crypto">("stock");
  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [showHero, setShowHero] = useState(true);

  const addToast = useCallback((msg: string, type: Toast["type"] = "info") => {
    const id = ++toastIdRef.current;
    setToasts((prev) => [...prev, { id, msg, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  const fetchAll = useCallback(async () => {
    try {
      const [s, sc, hist, perf, tradeList] = await Promise.all([
        getBotSummary().catch(() => null),
        getWatchlistScan().catch(() => null),
        getBotHistory().catch(() => []),
        getPerformance().catch(() => null),
        getTrades().catch(() => []),
      ]);
      if (s) setSummary(s);
      if (sc) setScan(sc);
      setHistory(hist);
      if (perf) setPerformance(perf);
      setTrades(tradeList);

      if (tradeList.length > 0) {
        for (const t of tradeList) {
          if (!prevTradeIdsRef.current.has(t.id) && t.status !== "open") {
            const pnlStr =
              t.realized_pnl != null
                ? ` P&L: ${t.realized_pnl >= 0 ? "+" : ""}$${t.realized_pnl.toFixed(2)}`
                : "";
            addToast(
              `${t.symbol} ${t.status.replace("_", " ")}${pnlStr}`,
              t.status === "took_profit" ? "success" : t.status === "stopped_out" ? "error" : "info",
            );
          }
        }
        prevTradeIdsRef.current = new Set(tradeList.map((t) => t.id));
      }

      getPositions()
        .then(setPositions)
        .catch(() => {});
      getPortfolioHistory()
        .then(setPortfolio)
        .catch(() => {});
      getWatchlist()
        .then((items) => setWatchlist(items ?? []))
        .catch(() => {});
      getAppConfig()
        .then((cfg) => setDemoMode(cfg?.demo_mode ?? false))
        .catch(() => {});
    } catch (err) {
      setError(String(err));
    }
  }, [addToast]);

  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      const ws = new WebSocket(`${WS_BASE_URL}/ws/market`);
      wsRef.current = ws;

      ws.onopen = () => setWsConnected(true);

      ws.onmessage = (event) => {
        try {
          const tick: MarketTick = JSON.parse(event.data);
          if (tick.type === "tick" && tick.symbol && tick.price != null) {
            setLivePrices((prev) => ({ ...prev, [tick.symbol!]: tick.price! }));
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        reconnectTimer = setTimeout(connect, 5000);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();
    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 30000);
    return () => clearInterval(id);
  }, [fetchAll]);

  useEffect(() => {
    getBacktestSymbols()
      .then((d) => {
        setBtSymbols(d.all);
        if (d.all.length > 0) setBtSymbol(d.all[0]);
      })
      .catch(() => {});
  }, []);

  const handleRunBacktest = useCallback(async () => {
    setBtLoading(true);
    setBtError(null);
    setBtResult(null);
    try {
      const result = await runBacktest({
        symbol: btSymbol,
        start: btStart,
        end: btEnd,
        stop_loss_pct: btSlPct,
        take_profit_pct: btTpPct,
      });
      setBtResult(result);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        String(err);
      setBtError(msg);
    } finally {
      setBtLoading(false);
    }
  }, [btSymbol, btStart, btEnd, btSlPct, btTpPct]);

  const cryptoWatchlistSymbols = watchlist
    .filter((w) => w.asset_class === "crypto")
    .map((w) => w.symbol);

  const cryptoPositions = positions.filter(
    (position) =>
      String((position as { asset_class?: string }).asset_class ?? "") === "crypto"
      || cryptoWatchlistSymbols.includes(position.symbol),
  );

  async function handleAddSymbol() {
    if (!newSymbol.trim()) return;
    setWatchlistLoading(true);
    try {
      await addWatchlistSymbol(newSymbol.trim().toUpperCase(), newSymbolClass);
      const updated = await getWatchlist().catch(() => []);
      setWatchlist(updated ?? []);
      setNewSymbol("");
      try {
        const scanResult = await getWatchlistScan();
        setScan(scanResult ?? null);
      } catch {
        // noop
      }
    } catch {
      // noop
    }
    setWatchlistLoading(false);
  }

  async function handleRemoveSymbol(symbol: string, assetClass: "stock" | "crypto") {
    setWatchlistLoading(true);
    try {
      await removeWatchlistSymbol(symbol, assetClass);
      const updated = await getWatchlist().catch(() => []);
      setWatchlist(updated ?? []);
      try {
        const scanResult = await getWatchlistScan();
        setScan(scanResult ?? null);
      } catch {
        // noop
      }
    } catch {
      // noop
    }
    setWatchlistLoading(false);
  }

  const portfolioChartData = portfolio?.timestamp?.map((ts, i) => ({
    time: new Date(ts * 1000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
    equity: portfolio.equity[i],
  })) ?? [];

  return (
    <div className="min-h-screen bg-gray-950 p-4">
      <ToastContainer toasts={toasts} />
      {showHero && (
        <div className="relative mb-6 rounded-xl border border-green-500/30 bg-gradient-to-br from-gray-900 via-gray-900 to-gray-800 p-6">
          <button
            onClick={() => setShowHero(false)}
            className="absolute right-4 top-4 text-gray-500 hover:text-white"
          >
            <X size={18} />
          </button>
          <div className="mb-4 flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-widest text-white">TRADEBOT PRO</h1>
            {demoMode && (
              <span className="rounded bg-yellow-500 px-2 py-0.5 text-xs font-bold text-black">
                DEMO MODE
              </span>
            )}
          </div>
          <p className="mb-6 text-sm text-gray-400">Automated Day Trading for Stocks &amp; Crypto</p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
              <div className="mb-2 flex items-center gap-2 text-green-400">
                <Shield size={16} />
                <span className="text-xs font-bold uppercase">Risk-Managed</span>
              </div>
              <p className="text-xs text-gray-400">Kill switches, position limits, daily loss caps</p>
            </div>
            <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
              <div className="mb-2 flex items-center gap-2 text-green-400">
                <BarChart2 size={16} />
                <span className="text-xs font-bold uppercase">Backtested Signals</span>
              </div>
              <p className="text-xs text-gray-400">Walk-forward tested, no look-ahead bias</p>
            </div>
            <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
              <div className="mb-2 flex items-center gap-2 text-green-400">
                <Zap size={16} />
                <span className="text-xs font-bold uppercase">Real-Time Alerts</span>
              </div>
              <p className="text-xs text-gray-400">Slack, Discord &amp; email trade notifications</p>
            </div>
          </div>
        </div>
      )}

      <div className="mb-6 flex flex-col gap-3 border-b border-gray-800 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Activity className="w-6 h-6 text-green-400" />
          <h1 className="text-xl font-bold tracking-wider text-white">TRADING BOT</h1>
          {demoMode && (
            <span className="rounded bg-yellow-500 px-2 py-0.5 text-xs font-bold text-black">DEMO</span>
          )}
          {summary && <StatusBadge status={summary.status} />}
          <span
            title={wsConnected ? "Live feed connected" : "Live feed disconnected"}
            className={`inline-flex items-center gap-1 text-xs ${wsConnected ? "text-green-400" : "text-gray-600"}`}
          >
            {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {wsConnected ? "LIVE" : "OFFLINE"}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/settings"
            className="rounded border border-gray-700 bg-gray-900 px-3 py-1.5 text-xs font-bold text-white hover:border-gray-600"
          >
            SETTINGS
          </Link>
          <label className="mr-2 flex items-center gap-2 cursor-pointer text-xs text-gray-400 sm:mr-4">
            <span className="hidden sm:inline">KILL SWITCH</span>
            <input
              type="checkbox"
              checked={killSwitch}
              onChange={async (e) => {
                setKillSwitchState(e.target.checked);
                await setKillSwitch(e.target.checked).catch(() => {});
              }}
              className="accent-red-500 w-4 h-4"
            />
          </label>
          <button
            onClick={() => startBot().then(fetchAll).catch(() => {})}
            className="flex items-center gap-1 bg-green-700 hover:bg-green-600 px-3 py-1.5 rounded text-xs font-bold text-white"
          >
            <Play className="w-3 h-3" /> START
          </button>
          <button
            onClick={() => pauseBot().then(fetchAll).catch(() => {})}
            className="flex items-center gap-1 bg-yellow-700 hover:bg-yellow-600 px-3 py-1.5 rounded text-xs font-bold text-white"
          >
            <Pause className="w-3 h-3" /> PAUSE
          </button>
          <button
            onClick={() => stopBot().then(fetchAll).catch(() => {})}
            className="flex items-center gap-1 bg-red-800 hover:bg-red-700 px-3 py-1.5 rounded text-xs font-bold text-white"
          >
            <Square className="w-3 h-3" /> STOP
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 text-red-400 text-xs bg-red-950 border border-red-800 rounded p-3">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <MetricCard
          label="ACCOUNT EQUITY"
          value={
            summary?.equity != null
              ? `$${summary.equity.toLocaleString("en-US", { minimumFractionDigits: 2 })}`
              : "—"
          }
          sub="Alpaca paper"
        />
        <MetricCard
          label="TRADES TODAY"
          value={summary?.trades_today ?? 0}
        />
        <MetricCard
          label="ERRORS TODAY"
          value={summary?.errors_today ?? 0}
        />
        <MetricCard
          label="LAST SCAN"
          value={
            summary?.last_scan_at
              ? new Date(summary.last_scan_at).toLocaleTimeString()
              : "—"
          }
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <MetricCard
          label="WIN RATE"
          value={performance ? `${(performance.win_rate * 100).toFixed(1)}%` : "—"}
          sub={performance ? `${performance.total_trades} total trades` : undefined}
        />
        <MetricCard
          label="SHARPE RATIO"
          value={performance ? performance.sharpe.toFixed(2) : "—"}
        />
        <MetricCard
          label="MAX DRAWDOWN"
          value={performance ? `${(performance.max_drawdown * 100).toFixed(2)}%` : "—"}
        />
        <MetricCard
          label="WIN/LOSS RATIO"
          value={performance ? performance.ratio.toFixed(2) : "—"}
        />
      </div>

      {portfolioChartData.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded p-4 mb-6">
          <h2 className="text-xs text-gray-400 mb-3 font-bold tracking-wider">
            PORTFOLIO EQUITY
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={portfolioChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="time"
                tick={{ fill: "#6b7280", fontSize: 10 }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#6b7280", fontSize: 10 }}
                tickLine={false}
                width={70}
                tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#111827",
                  border: "1px solid #374151",
                  borderRadius: 4,
                  fontSize: 12,
                }}
                formatter={(v) => [`$${Number(v ?? 0).toFixed(2)}`, "Equity"]}
              />
              <Line
                type="monotone"
                dataKey="equity"
                stroke="#22c55e"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="mb-6 rounded-xl border border-gray-800 bg-gray-900 p-4">
        <div className="mb-4 flex items-center gap-2">
          <Bitcoin size={18} className="text-yellow-400" />
          <h2 className="text-sm font-bold uppercase tracking-widest text-white">Crypto Portfolio</h2>
        </div>
        {cryptoPositions.length === 0 ? (
          <div className="text-sm text-gray-500">
            No open crypto positions.{" "}
            {watchlist.filter((w) => w.asset_class === "crypto").length > 0 && (
              <span>
                Watching{" "}
                {watchlist.filter((w) => w.asset_class === "crypto").map((w) => w.symbol).join(", ")}
              </span>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500">
                  <th className="pb-2 pr-4">SYMBOL</th>
                  <th className="pb-2 pr-4">QTY</th>
                  <th className="pb-2 pr-4">AVG ENTRY</th>
                  <th className="pb-2 pr-4">CURRENT</th>
                  <th className="pb-2">P&amp;L</th>
                </tr>
              </thead>
              <tbody>
                {cryptoPositions.map((position) => {
                  const pnl = parseFloat(position.unrealized_pl ?? "0");
                  return (
                    <tr key={position.symbol} className="border-t border-gray-800">
                      <td className="py-2 pr-4 font-mono text-yellow-400">{position.symbol}</td>
                      <td className="py-2 pr-4 text-gray-300">{position.qty ?? "0"}</td>
                      <td className="py-2 pr-4 text-gray-300">${parseFloat(position.avg_entry_price ?? "0").toFixed(2)}</td>
                      <td className="py-2 pr-4 text-gray-300">${parseFloat(livePrices[position.symbol]?.toString() ?? position.current_price ?? "0").toFixed(2)}</td>
                      <td className={`py-2 font-mono ${pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded p-4 mb-6 overflow-x-auto">
        <h2 className="text-xs text-gray-400 mb-3 font-bold tracking-wider">
          WATCHLIST SCANNER
          {scan?.scanned_at && (
            <span className="ml-2 text-gray-600 font-normal">
              {new Date(scan.scanned_at).toLocaleTimeString()}
            </span>
          )}
        </h2>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left py-1 pr-4">SYMBOL</th>
              <th className="hidden py-1 pr-4 text-left sm:table-cell">CLASS</th>
              <th className="text-right py-1 pr-4">LIVE</th>
              <th className="text-right py-1 pr-4">SCORE</th>
              <th className="hidden py-1 pr-4 text-left sm:table-cell">TIMEFRAMES</th>
              <th className="text-left py-1 pr-4">SIDE</th>
              <th className="text-center py-1">TRADE?</th>
            </tr>
          </thead>
          <tbody>
            {(scan?.results ?? []).map((r) => (
              <tr
                key={r.symbol}
                className={`border-b border-gray-800/50 ${r.should_trade ? "bg-green-950/30" : ""}`}
              >
                <td className="py-1.5 pr-4 font-bold text-white">{r.symbol}</td>
                <td className="hidden py-1.5 pr-4 text-gray-400 sm:table-cell">{r.asset_class}</td>
                <td className="py-1.5 pr-4 text-right font-mono text-cyan-400">
                  {livePrices[r.symbol] != null ? `$${livePrices[r.symbol].toFixed(2)}` : <span className="text-gray-700">—</span>}
                </td>
                <td className="py-1.5 pr-4 text-right">
                  <span className={r.aggregate_score >= 0.6 ? "text-green-400" : r.aggregate_score >= 0.3 ? "text-yellow-400" : "text-gray-500"}>
                    {(r.aggregate_score * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="hidden py-1.5 pr-4 text-gray-400 sm:table-cell">{r.fired_timeframes.join(", ") || "—"}</td>
                <td className="py-1.5 pr-4">
                  <SideIcon side={r.suggested_side} />
                  <span
                    className={`ml-1 ${r.suggested_side === "buy" ? "text-green-400" : r.suggested_side === "sell" ? "text-red-400" : "text-gray-500"}`}
                  >
                    {r.suggested_side.toUpperCase()}
                  </span>
                </td>
                <td className="py-1.5 text-center">
                  {r.should_trade ? (
                    <span className="text-green-400 font-bold">YES</span>
                  ) : (
                    <span className="text-gray-600">—</span>
                  )}
                </td>
              </tr>
            ))}
            {(scan?.results ?? []).length === 0 && (
              <tr>
                <td colSpan={7} className="py-4 text-center text-gray-600">
                  No scan data
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mb-6 rounded-xl border border-gray-800 bg-gray-900 p-4">
        <h2 className="mb-4 text-sm font-bold uppercase tracking-widest text-white">Watchlist Manager</h2>
        <div className="mb-4 flex flex-wrap gap-2">
          {watchlist.map((item) => (
            <span
              key={`${item.symbol}-${item.asset_class}`}
              className={`flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold ${
                item.asset_class === "crypto"
                  ? "border border-yellow-500/40 bg-yellow-500/10 text-yellow-300"
                  : "border border-indigo-500/40 bg-indigo-500/10 text-indigo-300"
              }`}
            >
              {item.symbol}
              <button
                onClick={() => handleRemoveSymbol(item.symbol, item.asset_class)}
                disabled={watchlistLoading}
                className="ml-1 text-gray-400 hover:text-white disabled:opacity-50"
              >
                <X size={12} />
              </button>
            </span>
          ))}
          {watchlist.length === 0 && <span className="text-xs text-gray-500">No symbols in watchlist</span>}
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={newSymbol}
            onChange={(e) => setNewSymbol((e.target.value ?? "").toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleAddSymbol()}
            placeholder="e.g. MSFT"
            disabled={watchlistLoading}
            className="w-32 rounded border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white placeholder-gray-600 focus:border-green-500 focus:outline-none disabled:opacity-50"
          />
          <select
            value={newSymbolClass}
            onChange={(e) => setNewSymbolClass((e.target.value as "stock" | "crypto") ?? "stock")}
            disabled={watchlistLoading}
            className="rounded border border-gray-700 bg-gray-800 px-2 py-1.5 text-sm text-white focus:border-green-500 focus:outline-none disabled:opacity-50"
          >
            <option value="stock">Stock</option>
            <option value="crypto">Crypto</option>
          </select>
          <button
            onClick={handleAddSymbol}
            disabled={watchlistLoading || !newSymbol.trim()}
            className="flex items-center gap-1 rounded bg-green-600 px-3 py-1.5 text-sm font-bold text-white hover:bg-green-500 disabled:opacity-50"
          >
            <Plus size={14} />
            Add
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded p-4 overflow-x-auto">
          <h2 className="text-xs text-gray-400 mb-3 font-bold tracking-wider">
            OPEN POSITIONS
          </h2>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-1 pr-3">SYMBOL</th>
                <th className="text-right py-1 pr-3">QTY</th>
                <th className="text-right py-1 pr-3">AVG</th>
                <th className="text-right py-1 pr-3">CURR</th>
                <th className="text-right py-1">P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const pnl = parseFloat(p.unrealized_pl);
                return (
                  <tr key={p.symbol} className="border-b border-gray-800/50">
                    <td className="py-1.5 pr-3 font-bold text-white">{p.symbol}</td>
                    <td className="py-1.5 pr-3 text-right text-gray-300">{p.qty}</td>
                    <td className="py-1.5 pr-3 text-right text-gray-300">
                      ${parseFloat(p.avg_entry_price).toFixed(2)}
                    </td>
                    <td className="py-1.5 pr-3 text-right text-gray-300">
                      ${parseFloat(p.current_price).toFixed(2)}
                    </td>
                    <td className={`py-1.5 text-right font-bold ${pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}
                    </td>
                  </tr>
                );
              })}
              {positions.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-gray-600">
                    No open positions
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded p-4 overflow-x-auto">
          <h2 className="text-xs text-gray-400 mb-3 font-bold tracking-wider">
            RECENT BOT ORDERS
          </h2>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-1 pr-3">SYMBOL</th>
                <th className="text-left py-1 pr-3">SIDE</th>
                <th className="text-right py-1 pr-3">QTY</th>
                <th className="text-right py-1 pr-3">FILL</th>
                <th className="text-left py-1">TIME</th>
              </tr>
            </thead>
            <tbody>
              {history.map((o) => (
                <tr key={o.id} className="border-b border-gray-800/50">
                  <td className="py-1.5 pr-3 font-bold text-white">{o.symbol}</td>
                  <td className={`py-1.5 pr-3 ${o.side === "buy" ? "text-green-400" : "text-red-400"}`}>
                    {o.side.toUpperCase()}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-gray-300">{o.quantity}</td>
                  <td className="py-1.5 pr-3 text-right text-gray-300">{o.fill_price > 0 ? `$${o.fill_price.toFixed(2)}` : "—"}</td>
                  <td className="py-1.5 text-gray-400">{new Date(o.created_at).toLocaleTimeString()}</td>
                </tr>
              ))}
              {history.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-gray-600">
                    No orders yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded p-4 mb-6">
        <h2 className="text-xs text-gray-400 mb-3 font-bold tracking-wider">TRADE JOURNAL</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left py-1 pr-3">SYMBOL</th>
              <th className="text-left py-1 pr-3">SIDE</th>
              <th className="text-right py-1 pr-3">ENTRY</th>
              <th className="text-right py-1 pr-3">EXIT</th>
              <th className="hidden py-1 pr-3 text-right sm:table-cell">SL</th>
              <th className="hidden py-1 pr-3 text-right sm:table-cell">TP</th>
              <th className="text-right py-1 pr-3">P&amp;L</th>
              <th className="text-left py-1 pr-3">STATUS</th>
              <th className="hidden py-1 text-left sm:table-cell">OPENED</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => {
              const statusColors: Record<string, string> = {
                open: "text-yellow-400",
                closed: "text-gray-400",
                took_profit: "text-green-400",
                stopped_out: "text-red-400",
              };
              const pnlColor = t.realized_pnl == null ? "text-gray-500" : t.realized_pnl >= 0 ? "text-green-400" : "text-red-400";
              return (
                <tr key={t.id} className="border-b border-gray-800/50">
                  <td className="py-1.5 pr-3 font-bold text-white">{t.symbol}</td>
                  <td className={`py-1.5 pr-3 ${t.side === "buy" ? "text-green-400" : "text-red-400"}`}>
                    {t.side.toUpperCase()}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-gray-300">${t.entry_price.toFixed(4)}</td>
                  <td className="py-1.5 pr-3 text-right text-gray-300">{t.exit_price != null ? `$${t.exit_price.toFixed(4)}` : "—"}</td>
                  <td className="hidden py-1.5 pr-3 text-right text-red-400/70 sm:table-cell">${t.stop_loss_price.toFixed(4)}</td>
                  <td className="hidden py-1.5 pr-3 text-right text-green-400/70 sm:table-cell">${t.take_profit_price.toFixed(4)}</td>
                  <td className={`py-1.5 pr-3 text-right font-bold ${pnlColor}`}>
                    {t.realized_pnl != null ? `${t.realized_pnl >= 0 ? "+" : ""}${t.realized_pnl.toFixed(2)}` : "—"}
                  </td>
                  <td className={`py-1.5 pr-3 ${statusColors[t.status] ?? "text-gray-400"}`}>
                    {t.status.replace("_", " ").toUpperCase()}
                  </td>
                  <td className="hidden py-1.5 text-gray-500 sm:table-cell">{new Date(t.opened_at).toLocaleTimeString()}</td>
                </tr>
              );
            })}
            {trades.length === 0 && (
              <tr>
                <td colSpan={9} className="py-4 text-center text-gray-600">
                  No trade journal entries yet
                </td>
              </tr>
            )}
          </tbody>
          </table>
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded p-4 mb-6">
        <h2 className="text-xs text-gray-400 mb-4 font-bold tracking-wider">STRATEGY BACKTEST</h2>
        <div className="flex flex-wrap gap-3 mb-4">
          <div className="flex flex-col gap-1">
            <label className="text-gray-500 text-xs">SYMBOL</label>
            <select value={btSymbol} onChange={(e) => setBtSymbol(e.target.value)} className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white">
              {btSymbols.length > 0 ? btSymbols.map((s) => <option key={s}>{s}</option>) : <option>{btSymbol}</option>}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-gray-500 text-xs">START</label>
            <input type="date" value={btStart} onChange={(e) => setBtStart(e.target.value)} className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-gray-500 text-xs">END</label>
            <input type="date" value={btEnd} onChange={(e) => setBtEnd(e.target.value)} className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-gray-500 text-xs">SL %</label>
            <input type="number" min={0.1} max={20} step={0.1} value={btSlPct} onChange={(e) => setBtSlPct(parseFloat(e.target.value))} className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white w-20" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-gray-500 text-xs">TP %</label>
            <input type="number" min={0.1} max={50} step={0.1} value={btTpPct} onChange={(e) => setBtTpPct(parseFloat(e.target.value))} className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white w-20" />
          </div>
          <div className="flex items-end">
            <button onClick={handleRunBacktest} disabled={btLoading} className="bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700 px-4 py-1.5 rounded text-xs font-bold text-white">
              {btLoading ? "RUNNING…" : "RUN BACKTEST"}
            </button>
          </div>
        </div>

        {btError && (
          <div className="flex items-center gap-2 text-red-400 text-xs bg-red-950 border border-red-800 rounded p-3 mb-4">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            {btError}
          </div>
        )}

        {btResult && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
              <MetricCard label="TRADES" value={btResult.metrics.total_trades} sub={`${btResult.total_bars} bars`} />
              <MetricCard label="WIN RATE" value={`${(btResult.metrics.win_rate * 100).toFixed(1)}%`} />
              <MetricCard
                label="TOTAL P&L"
                value={btResult.metrics.total_pnl >= 0 ? `+$${btResult.metrics.total_pnl.toFixed(2)}` : `-$${Math.abs(btResult.metrics.total_pnl).toFixed(2)}`}
                sub={`end equity $${btResult.metrics.ending_equity.toLocaleString()}`}
              />
              <MetricCard label="SHARPE" value={btResult.metrics.sharpe.toFixed(2)} />
              <MetricCard label="MAX DRAWDOWN" value={`${(btResult.metrics.max_drawdown * 100).toFixed(2)}%`} />
            </div>

            {btResult.equity_curve.length > 1 && (
              <div className="mb-4">
                <div className="text-xs text-gray-500 mb-2">EQUITY CURVE</div>
                <ResponsiveContainer width="100%" height={160}>
                  <LineChart
                    data={btResult.equity_curve.map((eq, idx) => ({ idx, eq }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                    <XAxis dataKey="idx" hide />
                    <YAxis
                      tick={{ fill: "#6b7280", fontSize: 10 }}
                      tickLine={false}
                      width={70}
                      tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#111827",
                        border: "1px solid #374151",
                        borderRadius: 4,
                        fontSize: 11,
                      }}
                      formatter={(v) => [`$${Number(v ?? 0).toFixed(2)}`, "Equity"]}
                      labelFormatter={() => ""}
                    />
                    <Line
                      type="monotone"
                      dataKey="eq"
                      stroke="#3b82f6"
                      dot={false}
                      strokeWidth={2}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            <div className="overflow-x-auto">
              <div className="text-xs text-gray-500 mb-2">
                SIMULATED TRADES ({btResult.trades.length})
              </div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-800">
                    <th className="text-left py-1 pr-3">ENTRY DATE</th>
                    <th className="text-left py-1 pr-3">EXIT DATE</th>
                    <th className="text-right py-1 pr-3">ENTRY</th>
                    <th className="text-right py-1 pr-3">EXIT</th>
                    <th className="text-right py-1 pr-3">QTY</th>
                    <th className="text-right py-1 pr-3">P&amp;L</th>
                    <th className="text-left py-1 pr-3">STATUS</th>
                    <th className="text-left py-1">RULES FIRED</th>
                  </tr>
                </thead>
                <tbody>
                  {btResult.trades.map((t, i) => {
                    const statusColors: Record<string, string> = {
                      took_profit: "text-green-400",
                      stopped_out: "text-red-400",
                      closed: "text-gray-400",
                      open: "text-yellow-400",
                    };
                    const pnlColor = t.realized_pnl == null ? "text-gray-500" : t.realized_pnl >= 0 ? "text-green-400" : "text-red-400";
                    return (
                      <tr key={i} className="border-b border-gray-800/50">
                        <td className="py-1 pr-3 text-gray-300">{t.entry_date}</td>
                        <td className="py-1 pr-3 text-gray-400">{t.exit_date ?? "—"}</td>
                        <td className="py-1 pr-3 text-right text-gray-300">${t.entry_price.toFixed(2)}</td>
                        <td className="py-1 pr-3 text-right text-gray-300">{t.exit_price != null ? `$${t.exit_price.toFixed(2)}` : "—"}</td>
                        <td className="py-1 pr-3 text-right text-gray-400">{t.quantity}</td>
                        <td className={`py-1 pr-3 text-right font-bold ${pnlColor}`}>
                          {t.realized_pnl != null ? `${t.realized_pnl >= 0 ? "+" : ""}$${t.realized_pnl.toFixed(2)}` : "—"}
                        </td>
                        <td className={`py-1 pr-3 ${statusColors[t.status] ?? "text-gray-400"}`}>
                          {t.status.replace("_", " ").toUpperCase()}
                        </td>
                        <td className="py-1 text-gray-600 text-xs">{t.fired_rules.join(", ") || "—"}</td>
                      </tr>
                    );
                  })}
                  {btResult.trades.length === 0 && (
                    <tr>
                      <td colSpan={8} className="py-4 text-center text-gray-600">
                        No signals fired in this date range. Try a wider range or lower min_signal_score.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
