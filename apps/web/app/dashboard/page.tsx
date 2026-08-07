'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import { useAuth } from '../../lib/auth-context';
import {
  apiOptimize, apiRisk, apiBacktest,
  sampleReturns, sampleReturnMatrix,
  pct, fmt,
} from '../../lib/api';

type MetricCard = { label: string; value: string; delta?: string; variant: string };

export default function DashboardPage() {
  const { token, user, loading } = useAuth();
  const router = useRouter();

  const [metrics, setMetrics] = useState<MetricCard[]>([]);
  const [equityData, setEquityData] = useState<{ day: number; equity: number }[]>([]);
  const [computing, setComputing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!loading && !token) router.replace('/');
  }, [token, loading, router]);

  useEffect(() => {
    if (!token) return;
    loadDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function loadDashboard() {
    setComputing(true);
    setError('');
    try {
      const returns = sampleReturns(252);
      const retMatrix = sampleReturnMatrix(252, 3);

      const [riskResult, backtestResult, optimizeResult] = await Promise.all([
        apiRisk(token, returns, 0.95),
        apiBacktest(token, retMatrix, [0.5, 0.3, 0.2]),
        apiOptimize(
          token,
          [0.05, 0.07, 0.06],
          [[0.01, 0.002, 0.001], [0.002, 0.015, 0.003], [0.001, 0.003, 0.012]],
        ),
      ]);

      setMetrics([
        {
          label: 'Portfolio Return',
          value: pct(backtestResult.total_return),
          delta: `Ann. ${pct(backtestResult.annualised_return)}`,
          variant: backtestResult.total_return >= 0 ? 'card-ok' : 'card-bad',
        },
        {
          label: 'Sharpe Ratio',
          value: fmt(backtestResult.sharpe_ratio, 3),
          delta: `Ann. vol ${pct(backtestResult.annualised_volatility)}`,
          variant: 'card-accent',
        },
        {
          label: 'Max Drawdown',
          value: pct(backtestResult.max_drawdown),
          delta: `VaR 95% ${pct(riskResult.historical_var)}`,
          variant: 'card-bad',
        },
        {
          label: 'MVE Top Weight',
          value: pct(Math.max(...optimizeResult.weights)),
          delta: `${optimizeResult.n_assets} assets`,
          variant: 'card-warn',
        },
      ]);

      setEquityData(
        backtestResult.equity.map((v, i) => ({ day: i + 1, equity: parseFloat(v.toFixed(4)) })),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard');
    } finally {
      setComputing(false);
    }
  }

  if (loading || !token) return null;

  return (
    <div className="page">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div className="page-title">Dashboard</div>
            <div className="page-subtitle">
              Welcome back, <strong>{user?.username}</strong> · Live quant metrics
            </div>
          </div>
          <button className="secondary" onClick={loadDashboard} disabled={computing}>
            {computing ? <><span className="spinner" />Refreshing…</> : (
              <><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.91"/></svg>Refresh</>
            )}
          </button>
        </div>
      </div>

      {error && <div className="alert alert-bad" style={{ marginBottom: 20 }}>{error}</div>}

      {/* KPI cards */}
      <div className="grid-4" style={{ marginBottom: 24 }}>
        {computing
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="card" style={{ height: 96, opacity: 0.4 }} />
            ))
          : metrics.map((m) => (
              <div key={m.label} className={`card ${m.variant}`}>
                <div className="card-title">{m.label}</div>
                <div className="card-value">{m.value}</div>
                {m.delta && <div className="card-delta">{m.delta}</div>}
              </div>
            ))}
      </div>

      {/* Equity curve chart */}
      <div className="card col-span-full" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <div className="card-title">Equity Curve</div>
            <div style={{ fontSize: 12, color: 'var(--subtle)' }}>
              60/30/20 weighted strategy · 252-day simulation
            </div>
          </div>
          <span className="badge badge-accent">Simulated</span>
        </div>
        {equityData.length > 0 ? (
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={equityData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4f8ef7" stopOpacity={0.25}/>
                  <stop offset="95%" stopColor="#4f8ef7" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1e2d4a" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="day" stroke="#4e6485" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis stroke="#4e6485" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(v) => v.toFixed(2)} />
              <Tooltip
                contentStyle={{ background: '#0e1628', border: '1px solid #1e2d4a', borderRadius: 8, fontSize: 12 }}
                formatter={(v) => [typeof v === 'number' ? v.toFixed(4) : v, 'Equity']}
                labelFormatter={(l) => `Day ${l}`}
              />
              <Area type="monotone" dataKey="equity" stroke="#4f8ef7" strokeWidth={2} fill="url(#eqGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ height: 240, display: 'grid', placeItems: 'center', color: 'var(--subtle)' }}>
            {computing ? <span className="spinner" style={{ width: 24, height: 24 }} /> : 'No data'}
          </div>
        )}
      </div>

      {/* Info cards row */}
      <div className="grid-2">
        <div className="card">
          <div className="card-title">Platform</div>
          <table style={{ marginTop: 8 }}>
            <tbody>
              {[
                ['Version', 'v0.6.0-alpha'],
                ['Auth', 'JWT + Redis refresh tokens'],
                ['RBAC', 'analyst, quant, admin'],
                ['Quant engine', 'NumPy / SciPy (OLS, MV, VaR)'],
                ['AI', 'IsolationForest + lexicon sentiment'],
              ].map(([k, v]) => (
                <tr key={k}>
                  <td style={{ color: 'var(--subtle)', width: 120 }}>{k}</td>
                  <td>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="card-title">Quick Links</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
            {[
              { label: 'Portfolio Optimization →', href: '/quant' },
              { label: 'Backtesting →', href: '/quant' },
              { label: 'Factor Model →', href: '/quant' },
              { label: 'Anomaly Detection →', href: '/ai' },
              { label: 'Sentiment Analysis →', href: '/ai' },
            ].map((l) => (
              <a
                key={l.label}
                href={l.href}
                style={{ color: 'var(--accent)', fontSize: 13.5, textDecoration: 'none' }}
              >
                {l.label}
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
