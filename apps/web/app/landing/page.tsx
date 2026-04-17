import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-gray-950 font-mono text-white">
      <section className="flex flex-col items-center justify-center px-6 py-24 text-center">
        <div className="mb-4 rounded-full border border-green-500/30 bg-green-500/10 px-4 py-1 text-xs font-bold uppercase tracking-widest text-green-400">
          Automated Trading Platform
        </div>
        <h1 className="mb-4 text-4xl font-bold tracking-tight md:text-6xl">
          Trade Smarter,{" "}
          <span className="text-green-400">Not Harder</span>
        </h1>
        <p className="mb-8 max-w-xl text-lg text-gray-400">
          Automated signals for stocks and crypto. Walk-forward backtested rules, real-time execution,
          and risk controls that protect your capital.
        </p>
        <div className="flex gap-4">
          <Link
            href="/"
            className="rounded-lg bg-green-500 px-6 py-3 font-bold text-black hover:bg-green-400"
          >
            Launch Dashboard →
          </Link>
          <button className="rounded-lg border border-gray-700 px-6 py-3 font-bold text-gray-300 hover:border-gray-500 hover:text-white">
            Watch Demo
          </button>
        </div>
      </section>

      <section className="border-y border-gray-800 bg-gray-900 py-8">
        <div className="mx-auto grid max-w-4xl grid-cols-3 gap-8 text-center">
          <div>
            <div className="text-3xl font-bold text-green-400">8</div>
            <div className="mt-1 text-xs uppercase tracking-widest text-gray-500">Signal Rules</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-green-400">65%+</div>
            <div className="mt-1 text-xs uppercase tracking-widest text-gray-500">Backtest Win Rate</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-green-400">24/7</div>
            <div className="mt-1 text-xs uppercase tracking-widest text-gray-500">Automated Trading</div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-20">
        <h2 className="mb-12 text-center text-2xl font-bold uppercase tracking-widest">Features</h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { title: "Automated Bot", desc: "Scans your watchlist every 60 seconds, fires bracket orders automatically" },
            { title: "Multi-Timeframe", desc: "Confirms signals across 5m, 15m, 1h before entering" },
            { title: "Risk Engine", desc: "Per-trade sizing, daily loss caps, kill switches with one click" },
            { title: "Backtesting", desc: "Walk-forward tested on the same signal rules the live bot uses" },
            { title: "Real-Time Feed", desc: "WebSocket live prices, Slack/email trade alerts" },
            { title: "Crypto + Stocks", desc: "Supports BTC, ETH, SOL and all major equities via Alpaca" },
          ].map((f) => (
            <div
              key={f.title}
              className="rounded-xl border border-gray-800 bg-gray-900 p-6"
            >
              <h3 className="mb-2 font-bold text-green-400">{f.title}</h3>
              <p className="text-sm text-gray-400">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-gray-900 py-20">
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="mb-12 text-center text-2xl font-bold uppercase tracking-widest">Pricing</h2>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            <div className="rounded-xl border border-gray-800 bg-gray-950 p-6">
              <div className="mb-1 text-xs uppercase tracking-widest text-gray-500">Free</div>
              <div className="mb-1 text-2xl font-bold">Paper Trading</div>
              <div className="mb-6 text-3xl font-bold text-white">$0<span className="text-base font-normal text-gray-500">/mo</span></div>
              <ul className="space-y-2 text-sm text-gray-400">
                <li>✓ Paper trading only</li>
                <li>✓ 5 symbols</li>
                <li>✓ Mock signals</li>
              </ul>
            </div>
            <div className="rounded-xl border-2 border-green-500 bg-gray-950 p-6">
              <div className="mb-1 text-xs font-bold uppercase tracking-widest text-green-400">Pro — Most Popular</div>
              <div className="mb-1 text-2xl font-bold">Go Live</div>
              <div className="mb-6 text-3xl font-bold text-white">$49<span className="text-base font-normal text-gray-500">/mo</span></div>
              <ul className="space-y-2 text-sm text-gray-400">
                <li>✓ Live trading</li>
                <li>✓ 20 symbols</li>
                <li>✓ Full backtesting</li>
                <li>✓ Email alerts</li>
              </ul>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950 p-6">
              <div className="mb-1 text-xs uppercase tracking-widest text-gray-500">Trader</div>
              <div className="mb-1 text-2xl font-bold">Full Power</div>
              <div className="mb-6 text-3xl font-bold text-white">$99<span className="text-base font-normal text-gray-500">/mo</span></div>
              <ul className="space-y-2 text-sm text-gray-400">
                <li>✓ Unlimited symbols</li>
                <li>✓ Slack alerts</li>
                <li>✓ Advanced analytics</li>
                <li>✓ Priority support</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-gray-800 py-8 text-center text-sm text-gray-600">
        Built for serious traders. © 2025 TradebotPro.
      </footer>
    </main>
  );
}
