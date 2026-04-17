"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  getNotificationConfig,
  getRiskPolicy,
  testNotification,
  upsertNotificationConfig,
  upsertRiskPolicy,
  type NotificationConfig,
  type RiskPolicy,
} from "@/lib/api";
import { authMe, clearToken, getErrorMessage, type User } from "@/lib/auth";

type Tab = "risk" | "notifications" | "account";

const defaultRisk: RiskPolicy = {
  user_id: 0,
  max_risk_per_trade_pct: 1,
  max_daily_loss: 500,
  max_open_positions: 5,
  consecutive_loss_limit: 3,
  allowed_symbols: [],
  live_trading_enabled: false,
};

const defaultNotifications: NotificationConfig = {
  webhook_url: "",
  email_to: "",
  smtp_host: "smtp.gmail.com",
  smtp_port: 587,
  smtp_user: "",
  smtp_password: "",
  smtp_tls: true,
  notify_on_trade: true,
  notify_on_error: true,
  notify_on_kill_switch: true,
  notify_on_daily_summary: true,
  is_active: true,
};

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("risk");
  const [user, setUser] = useState<User | null>(null);
  const [risk, setRisk] = useState<RiskPolicy>(defaultRisk);
  const [notifications, setNotifications] = useState<NotificationConfig>(defaultNotifications);
  const [allowedSymbolsText, setAllowedSymbolsText] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [riskMessage, setRiskMessage] = useState<string | null>(null);
  const [riskError, setRiskError] = useState<string | null>(null);
  const [notifMessage, setNotifMessage] = useState<string | null>(null);
  const [notifError, setNotifError] = useState<string | null>(null);
  const [testMessage, setTestMessage] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const me = await authMe();
        if (!active) return;
        setUser(me);

        try {
          const policy = await getRiskPolicy(me.id);
          if (!active) return;
          const nextRisk = policy ? { ...policy } : { ...defaultRisk, user_id: me.id };
          setRisk(nextRisk);
          setAllowedSymbolsText(nextRisk.allowed_symbols.join(","));
        } catch (err: unknown) {
          if (!active) return;
          setLoadError(getErrorMessage(err, "Failed to load risk policy"));
        }

        try {
          const config = await getNotificationConfig();
          if (!active) return;
          setNotifications(config ? { ...defaultNotifications, ...config, smtp_password: "" } : defaultNotifications);
        } catch (err: unknown) {
          if (!active) return;
          setLoadError(getErrorMessage(err, "Failed to load notification config"));
        }
      } catch {
        clearToken();
      } finally {
        if (active) setLoading(false);
      }
    })().catch(() => {
      if (!active) return;
      clearToken();
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, []);

  async function saveRisk(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setRiskMessage(null);
    setRiskError(null);
    try {
      const payload: RiskPolicy = {
        ...risk,
        user_id: user?.id ?? risk.user_id,
        allowed_symbols: allowedSymbolsText
          .split(",")
          .map((v) => v.trim().toUpperCase())
          .filter(Boolean),
      };
      const saved = await upsertRiskPolicy(payload);
      setRisk(saved);
      setAllowedSymbolsText(saved.allowed_symbols.join(","));
      setRiskMessage("Risk policy saved successfully");
    } catch (err: unknown) {
      setRiskError(getErrorMessage(err, "Failed to save risk policy"));
    }
  }

  async function saveNotifications(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setNotifMessage(null);
    setNotifError(null);
    try {
      const saved = await upsertNotificationConfig(notifications);
      setNotifications({ ...notifications, ...saved, smtp_password: "" });
      setNotifMessage("Notification settings saved successfully");
    } catch (err: unknown) {
      setNotifError(getErrorMessage(err, "Failed to save notification settings"));
    }
  }

  async function sendTestNotification() {
    setTestMessage(null);
    setTestError(null);
    try {
      const res = await testNotification();
      setTestMessage(res?.detail ?? "Test notification sent");
    } catch (err: unknown) {
      setTestError(getErrorMessage(err, "Failed to send test notification"));
    }
  }

  function signOut() {
    clearToken();
    setUser(null);
  }

  return (
    <div className="min-h-screen bg-gray-950 p-4 text-white">
      <div className="mx-auto w-full max-w-4xl space-y-4">
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
          <h1 className="text-xl font-bold">Settings</h1>
          <p className="text-sm text-gray-400">Manage your account, risk, and notifications</p>
        </div>

        <div className="flex flex-wrap gap-2">
          {(["risk", "notifications", "account"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`rounded px-3 py-2 text-sm capitalize ${
                activeTab === tab ? "bg-green-600 text-white" : "bg-gray-900 text-gray-300"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {loading && <div className="rounded border border-gray-800 bg-gray-900 p-4 text-sm text-gray-300">Loading settings...</div>}
        {loadError && <div className="rounded border border-red-700 bg-red-900/30 p-4 text-sm text-red-300">{loadError}</div>}

        {!loading && activeTab === "risk" && (
          <form onSubmit={saveRisk} className="space-y-4 rounded-xl border border-gray-800 bg-gray-900 p-4">
            {riskMessage && <div className="rounded border border-green-700 bg-green-900/30 p-3 text-sm text-green-300">{riskMessage}</div>}
            {riskError && <div className="rounded border border-red-700 bg-red-900/30 p-3 text-sm text-red-300">{riskError}</div>}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="text-sm">Max risk % per trade
                <input type="number" step="0.1" min="0.1" max="10" value={risk.max_risk_per_trade_pct} onChange={(e) => setRisk((prev) => ({ ...prev, max_risk_per_trade_pct: Number(e.target.value) }))} className="mt-1 w-full rounded border border-gray-800 bg-gray-950 px-3 py-2" />
              </label>
              <label className="text-sm">Max daily loss
                <input type="number" min="1" value={risk.max_daily_loss} onChange={(e) => setRisk((prev) => ({ ...prev, max_daily_loss: Number(e.target.value) }))} className="mt-1 w-full rounded border border-gray-800 bg-gray-950 px-3 py-2" />
              </label>
              <label className="text-sm">Max open positions
                <input type="number" min="1" max="100" value={risk.max_open_positions} onChange={(e) => setRisk((prev) => ({ ...prev, max_open_positions: Number(e.target.value) }))} className="mt-1 w-full rounded border border-gray-800 bg-gray-950 px-3 py-2" />
              </label>
              <label className="text-sm">Consecutive loss limit
                <input type="number" min="1" max="20" value={risk.consecutive_loss_limit} onChange={(e) => setRisk((prev) => ({ ...prev, consecutive_loss_limit: Number(e.target.value) }))} className="mt-1 w-full rounded border border-gray-800 bg-gray-950 px-3 py-2" />
              </label>
            </div>

            <label className="block text-sm">Allowed symbols (comma separated)
              <input type="text" value={allowedSymbolsText} onChange={(e) => setAllowedSymbolsText(e.target.value)} className="mt-1 w-full rounded border border-gray-800 bg-gray-950 px-3 py-2" placeholder="AAPL,NVDA,BTC/USD" />
            </label>

            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input type="checkbox" checked={risk.live_trading_enabled} onChange={(e) => setRisk((prev) => ({ ...prev, live_trading_enabled: e.target.checked }))} className="h-4 w-4 accent-green-500" />
              Live trading enabled
            </label>

            <button type="submit" className="rounded bg-green-600 px-4 py-2 text-sm font-semibold hover:bg-green-500">Save risk policy</button>
          </form>
        )}

        {!loading && activeTab === "notifications" && (
          <form onSubmit={saveNotifications} className="space-y-4 rounded-xl border border-gray-800 bg-gray-900 p-4">
            {notifMessage && <div className="rounded border border-green-700 bg-green-900/30 p-3 text-sm text-green-300">{notifMessage}</div>}
            {notifError && <div className="rounded border border-red-700 bg-red-900/30 p-3 text-sm text-red-300">{notifError}</div>}
            {testMessage && <div className="rounded border border-green-700 bg-green-900/30 p-3 text-sm text-green-300">{testMessage}</div>}
            {testError && <div className="rounded border border-red-700 bg-red-900/30 p-3 text-sm text-red-300">{testError}</div>}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="text-sm">Webhook URL
                <input type="text" value={notifications.webhook_url} onChange={(e) => setNotifications((prev) => ({ ...prev, webhook_url: e.target.value }))} className="mt-1 w-full rounded border border-gray-800 bg-gray-950 px-3 py-2" />
              </label>
              <label className="text-sm">Notification email
                <input type="email" value={notifications.email_to} onChange={(e) => setNotifications((prev) => ({ ...prev, email_to: e.target.value }))} className="mt-1 w-full rounded border border-gray-800 bg-gray-950 px-3 py-2" />
              </label>
              <label className="text-sm">SMTP host
                <input type="text" value={notifications.smtp_host} onChange={(e) => setNotifications((prev) => ({ ...prev, smtp_host: e.target.value }))} className="mt-1 w-full rounded border border-gray-800 bg-gray-950 px-3 py-2" />
              </label>
              <label className="text-sm">SMTP port
                <input type="number" value={notifications.smtp_port} onChange={(e) => setNotifications((prev) => ({ ...prev, smtp_port: Number(e.target.value) }))} className="mt-1 w-full rounded border border-gray-800 bg-gray-950 px-3 py-2" />
              </label>
              <label className="text-sm">SMTP user
                <input type="text" value={notifications.smtp_user} onChange={(e) => setNotifications((prev) => ({ ...prev, smtp_user: e.target.value }))} className="mt-1 w-full rounded border border-gray-800 bg-gray-950 px-3 py-2" />
              </label>
              <label className="text-sm">SMTP password
                <input type="password" value={notifications.smtp_password ?? ""} onChange={(e) => setNotifications((prev) => ({ ...prev, smtp_password: e.target.value }))} className="mt-1 w-full rounded border border-gray-800 bg-gray-950 px-3 py-2" />
              </label>
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {([
                ["smtp_tls", "Use TLS"],
                ["notify_on_trade", "Notify on trade"],
                ["notify_on_error", "Notify on error"],
                ["notify_on_kill_switch", "Notify on kill switch"],
                ["notify_on_daily_summary", "Notify on daily summary"],
                ["is_active", "Notifications active"],
              ] as const).map(([field, label]) => (
                <label key={field} className="flex items-center gap-2 text-sm text-gray-300">
                  <input
                    type="checkbox"
                    checked={Boolean(notifications[field])}
                    onChange={(e) => setNotifications((prev) => ({ ...prev, [field]: e.target.checked }))}
                    className="h-4 w-4 accent-green-500"
                  />
                  {label}
                </label>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <button type="submit" className="rounded bg-green-600 px-4 py-2 text-sm font-semibold hover:bg-green-500">Save notifications</button>
              <button type="button" onClick={() => { void sendTestNotification(); }} className="rounded border border-gray-700 bg-gray-800 px-4 py-2 text-sm font-semibold hover:bg-gray-700">Send test</button>
            </div>
          </form>
        )}

        {!loading && activeTab === "account" && (
          <div className="space-y-4 rounded-xl border border-gray-800 bg-gray-900 p-4">
            <div className="grid grid-cols-1 gap-2 text-sm text-gray-300">
              <div><span className="text-gray-500">Name:</span> {user?.full_name ?? "—"}</div>
              <div><span className="text-gray-500">Email:</span> {user?.email ?? "—"}</div>
              <div><span className="text-gray-500">Role:</span> {user?.role ?? "—"}</div>
            </div>
            <button onClick={signOut} className="rounded bg-green-600 px-4 py-2 text-sm font-semibold hover:bg-green-500">Sign out</button>
          </div>
        )}
      </div>
    </div>
  );
}
