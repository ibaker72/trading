"use client";

import { useEffect, useState, useCallback } from "react";
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
} from "lucide-react";
import {
  getBotSummary,
  getWatchlistScan,
  getPositions,
  getBotHistory,
  getPortfolioHistory,
  startBot,
  stopBot,
  pauseBot,
  setKillSwitch,
  type BotSummary,
  type WatchlistScanResult,
  type Position,
  type BotOrder,
  type PortfolioHistory,
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

export default function Dashboard() {
  const [summary, setSummary] = useState<BotSummary | null>(null);
  const [scan, setScan] = useState<WatchlistScanResult | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [history, setHistory] = useState<BotOrder[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioHistory | null>(null);
  const [killSwitch, setKillSwitchState] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [s, sc, hist] = await Promise.all([
        getBotSummary().catch(() => null),
        getWatchlistScan().catch(() => null),
        getBotHistory().catch(() => []),
      ]);
      if (s) setSummary(s);
      if (sc) setScan(sc);
      setHistory(hist);

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

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 30_000);
    return () => clearInterval(id);
  }, [fetchAll]);

  const portfolioChartData = portfolio?.timestamp?.map((ts, i) => ({
    time: new Date(ts * 1000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
    equity: portfolio.equity[i],
  })) ?? [];

  return (
    <div className="min-h-screen bg-gray-950 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 border-b border-gray-800 pb-4">
        <div className="flex items-center gap-3">
          <Activity className="w-6 h-6 text-green-400" />
          <h1 className="text-xl font-bold tracking-wider">TRADING BOT</h1>
          {summary && <StatusBadge status={summary.status} />}
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
                <td colSpan={6} className="py-4 text-center text-gray-600">
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
    </div>
  );
}
