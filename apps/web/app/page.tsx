"use client";

import { useEffect, useState, useCallback, useRef } from "react";
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
  if (side === "buy")
    return <TrendingUp className="inline w-4 h-4 text-green-400" />;
  if (side === "sell")
    return <TrendingDown className="inline w-4 h-4 text-red-400" />;
  return <Minus className="inline w-4 h-4 text-gray-400" />;
}

interface Toast {
  id: number;
  msg: string;
  type: "info" | "success" | "error";
}

function ToastContainer({ toasts }: { toasts: Toast[] }) {
  if (toasts.length === 0) return null;
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

  // Backtest state
  const [btSymbols, setBtSymbols] = useState<string[]>([]);
  const [btSymbol, setBtSymbol] = useState("AAPL");
  const [btStart, setBtStart] = useState("2024-01-01");
  const [btEnd, setBtEnd] = useState("2024-12-31");
  const [btSlPct, setBtSlPct] = useState(1.0);
  const [btTpPct, setBtTpPct] = useState(2.0);
  const [btResult, setBtResult] = useState<BacktestResult | null>(null);
  const [btLoading, setBtLoading] = useState(false);
  const [btError, setBtError] = useState<string | null>(null);

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

      // Toast on newly closed trades
      if (tradeList.length > 0) {
        for (const t of tradeList) {
          if (!prevTradeIdsRef.current.has(t.id) && t.status !== "open") {
            const pnlStr = t.realized_pnl != null
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
    } catch (err) {
      setError(String(err));
    }
  }, []);

  // WebSocket live price feed
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

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, []);

  // Periodic data refresh (30s fallback)
  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 30_000);
    return () => clearInterval(id);
  }, [fetchAll]);

  // Load backtest symbols once on mount
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
      {/* Header */}
      <div className="flex items-center justify-between mb-6 border-b border-gray-800 pb-4">
        <div className="flex items-center gap-3">
          <Activity className="w-6 h-6 text-green-400" />
          <h1 className="text-xl font-bold tracking-wider">TRADING BOT</h1>
          {summary && <StatusBadge status={summary.status} />}
          <span
            title={wsConnected ? "Live feed connected" : "Live feed disconnected"}
            className={`inline-flex items-center gap-1 text-xs ${wsConnected ? "text-green-400" : "text-gray-600"}`}
          >
            {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {wsConnected ? "LIVE" : "OFFLINE"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Kill switch */}
          <label className="flex items-center gap-2 text-xs text-gray-400 mr-4 cursor-pointer">
            <span>KILL SWITCH</span>
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
            className="flex items-center gap-1 bg-green-700 hover:bg-green-600 px-3 py-1.5 rounded text-xs font-bold"
          >
            <Play className="w-3 h-3" /> START
          </button>
          <button
            onClick={() => pauseBot().then(fetchAll).catch(() => {})}
            className="flex items-center gap-1 bg-yellow-700 hover:bg-yellow-600 px-3 py-1.5 rounded text-xs font-bold"
          >
            <Pause className="w-3 h-3" /> PAUSE
          </button>
          <button
            onClick={() => stopBot().then(fetchAll).catch(() => {})}
            className="flex items-center gap-1 bg-red-800 hover:bg-red-700 px-3 py-1.5 rounded text-xs font-bold"
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

      {/* Metric Cards */}
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
          sub={summary?.last_error ?? undefined}
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

      {/* Performance Cards */}
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
          sub={
            performance
              ? `avg win $${performance.avg_win.toFixed(2)} / loss $${performance.avg_loss.toFixed(2)}`
              : undefined
          }
        />
      </div>

      {/* Portfolio Chart */}
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
                formatter={(v: number) => [`$${v.toFixed(2)}`, "Equity"]}
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

      {/* Scanner Table */}
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
              <th className="text-left py-1 pr-4">CLASS</th>
              <th className="text-right py-1 pr-4">LIVE</th>
              <th className="text-right py-1 pr-4">SCORE</th>
              <th className="text-left py-1 pr-4">TIMEFRAMES</th>
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
                <td className="py-1.5 pr-4 font-bold">{r.symbol}</td>
                <td className="py-1.5 pr-4 text-gray-400">{r.asset_class}</td>
                <td className="py-1.5 pr-4 text-right font-mono text-cyan-400">
                  {livePrices[r.symbol] != null
                    ? `$${livePrices[r.symbol].toFixed(2)}`
                    : <span className="text-gray-700">—</span>}
                </td>
                <td className="py-1.5 pr-4 text-right">
                  <span
                    className={
                      r.aggregate_score >= 0.6
                        ? "text-green-400"
                        : r.aggregate_score >= 0.3
                        ? "text-yellow-400"
                        : "text-gray-500"
                    }
                  >
                    {(r.aggregate_score * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="py-1.5 pr-4 text-gray-400">
                  {r.fired_timeframes.join(", ") || "—"}
                </td>
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Open Positions */}
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
                <th className="text-right py-1">P&L</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const pnl = parseFloat(p.unrealized_pl);
                return (
                  <tr key={p.symbol} className="border-b border-gray-800/50">
                    <td className="py-1.5 pr-3 font-bold">{p.symbol}</td>
                    <td className="py-1.5 pr-3 text-right">{p.qty}</td>
                    <td className="py-1.5 pr-3 text-right">
                      ${parseFloat(p.avg_entry_price).toFixed(2)}
                    </td>
                    <td className="py-1.5 pr-3 text-right">
                      ${parseFloat(p.current_price).toFixed(2)}
                    </td>
                    <td
                      className={`py-1.5 text-right font-bold ${pnl >= 0 ? "text-green-400" : "text-red-400"}`}
                    >
                      {pnl >= 0 ? "+" : ""}
                      {pnl.toFixed(2)}
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

        {/* Recent Orders */}
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
                  <td className="py-1.5 pr-3 font-bold">{o.symbol}</td>
                  <td
                    className={`py-1.5 pr-3 ${o.side === "buy" ? "text-green-400" : "text-red-400"}`}
                  >
                    {o.side.toUpperCase()}
                  </td>
                  <td className="py-1.5 pr-3 text-right">{o.quantity}</td>
                  <td className="py-1.5 pr-3 text-right">
                    {o.fill_price > 0 ? `$${o.fill_price.toFixed(2)}` : "—"}
                  </td>
                  <td className="py-1.5 text-gray-400">
                    {new Date(o.created_at).toLocaleTimeString()}
                  </td>
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

      {/* Trade Journal */}
      <div className="bg-gray-900 border border-gray-800 rounded p-4 mb-6 overflow-x-auto">
        <h2 className="text-xs text-gray-400 mb-3 font-bold tracking-wider">
          TRADE JOURNAL
        </h2>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left py-1 pr-3">SYMBOL</th>
              <th className="text-left py-1 pr-3">SIDE</th>
              <th className="text-right py-1 pr-3">ENTRY</th>
              <th className="text-right py-1 pr-3">EXIT</th>
              <th className="text-right py-1 pr-3">SL</th>
              <th className="text-right py-1 pr-3">TP</th>
              <th className="text-right py-1 pr-3">P&L</th>
              <th className="text-left py-1 pr-3">STATUS</th>
              <th className="text-left py-1">OPENED</th>
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
              const pnlColor =
                t.realized_pnl == null
                  ? "text-gray-500"
                  : t.realized_pnl >= 0
                  ? "text-green-400"
                  : "text-red-400";
              return (
                <tr key={t.id} className="border-b border-gray-800/50">
                  <td className="py-1.5 pr-3 font-bold">{t.symbol}</td>
                  <td
                    className={`py-1.5 pr-3 ${t.side === "buy" ? "text-green-400" : "text-red-400"}`}
                  >
                    {t.side.toUpperCase()}
                  </td>
                  <td className="py-1.5 pr-3 text-right">
                    ${t.entry_price.toFixed(4)}
                  </td>
                  <td className="py-1.5 pr-3 text-right">
                    {t.exit_price != null ? `$${t.exit_price.toFixed(4)}` : "—"}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-red-400/70">
                    ${t.stop_loss_price.toFixed(4)}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-green-400/70">
                    ${t.take_profit_price.toFixed(4)}
                  </td>
                  <td className={`py-1.5 pr-3 text-right font-bold ${pnlColor}`}>
                    {t.realized_pnl != null
                      ? `${t.realized_pnl >= 0 ? "+" : ""}${t.realized_pnl.toFixed(2)}`
                      : "—"}
                  </td>
                  <td
                    className={`py-1.5 pr-3 ${statusColors[t.status] ?? "text-gray-400"}`}
                  >
                    {t.status.replace("_", " ").toUpperCase()}
                  </td>
                  <td className="py-1.5 text-gray-500">
                    {new Date(t.opened_at).toLocaleTimeString()}
                  </td>
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

      {/* ── Backtest Panel ─────────────────────────────────────── */}
      <div className="bg-gray-900 border border-gray-800 rounded p-4 mb-6">
        <h2 className="text-xs text-gray-400 mb-4 font-bold tracking-wider">
          STRATEGY BACKTEST
        </h2>

        {/* Controls */}
        <div className="flex flex-wrap gap-3 mb-4">
          <div className="flex flex-col gap-1">
            <label className="text-gray-500 text-xs">SYMBOL</label>
            <select
              value={btSymbol}
              onChange={(e) => setBtSymbol(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white"
            >
              {btSymbols.length > 0
                ? btSymbols.map((s) => <option key={s}>{s}</option>)
                : <option>{btSymbol}</option>}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-gray-500 text-xs">START</label>
            <input
              type="date"
              value={btStart}
              onChange={(e) => setBtStart(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-gray-500 text-xs">END</label>
            <input
              type="date"
              value={btEnd}
              onChange={(e) => setBtEnd(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-gray-500 text-xs">SL %</label>
            <input
              type="number"
              min={0.1}
              max={20}
              step={0.1}
              value={btSlPct}
              onChange={(e) => setBtSlPct(parseFloat(e.target.value))}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white w-20"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-gray-500 text-xs">TP %</label>
            <input
              type="number"
              min={0.1}
              max={50}
              step={0.1}
              value={btTpPct}
              onChange={(e) => setBtTpPct(parseFloat(e.target.value))}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white w-20"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={handleRunBacktest}
              disabled={btLoading}
              className="bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700 px-4 py-1.5 rounded text-xs font-bold"
            >
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
            {/* Metrics row */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
              <MetricCard
                label="TRADES"
                value={btResult.metrics.total_trades}
                sub={`${btResult.total_bars} bars`}
              />
              <MetricCard
                label="WIN RATE"
                value={`${(btResult.metrics.win_rate * 100).toFixed(1)}%`}
              />
              <MetricCard
                label="TOTAL P&L"
                value={
                  btResult.metrics.total_pnl >= 0
                    ? `+$${btResult.metrics.total_pnl.toFixed(2)}`
                    : `-$${Math.abs(btResult.metrics.total_pnl).toFixed(2)}`
                }
                sub={`end equity $${btResult.metrics.ending_equity.toLocaleString()}`}
              />
              <MetricCard
                label="SHARPE"
                value={btResult.metrics.sharpe.toFixed(2)}
              />
              <MetricCard
                label="MAX DRAWDOWN"
                value={`${(btResult.metrics.max_drawdown * 100).toFixed(2)}%`}
              />
            </div>

            {/* Equity curve */}
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
                      formatter={(v: number) => [`$${v.toFixed(2)}`, "Equity"]}
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

            {/* Trades table */}
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
                    <th className="text-right py-1 pr-3">P&L</th>
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
                    const pnlColor =
                      t.realized_pnl == null
                        ? "text-gray-500"
                        : t.realized_pnl >= 0
                        ? "text-green-400"
                        : "text-red-400";
                    return (
                      <tr key={i} className="border-b border-gray-800/50">
                        <td className="py-1 pr-3 text-gray-300">{t.entry_date}</td>
                        <td className="py-1 pr-3 text-gray-400">
                          {t.exit_date ?? "—"}
                        </td>
                        <td className="py-1 pr-3 text-right">
                          ${t.entry_price.toFixed(2)}
                        </td>
                        <td className="py-1 pr-3 text-right">
                          {t.exit_price != null
                            ? `$${t.exit_price.toFixed(2)}`
                            : "—"}
                        </td>
                        <td className="py-1 pr-3 text-right text-gray-400">
                          {t.quantity}
                        </td>
                        <td className={`py-1 pr-3 text-right font-bold ${pnlColor}`}>
                          {t.realized_pnl != null
                            ? `${t.realized_pnl >= 0 ? "+" : ""}$${t.realized_pnl.toFixed(2)}`
                            : "—"}
                        </td>
                        <td
                          className={`py-1 pr-3 ${statusColors[t.status] ?? "text-gray-400"}`}
                        >
                          {t.status.replace("_", " ").toUpperCase()}
                        </td>
                        <td className="py-1 text-gray-600 text-xs">
                          {t.fired_rules.join(", ") || "—"}
                        </td>
                      </tr>
                    );
                  })}
                  {btResult.trades.length === 0 && (
                    <tr>
                      <td colSpan={8} className="py-4 text-center text-gray-600">
                        No signals fired in this date range. Try a wider range or
                        lower min_signal_score.
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
