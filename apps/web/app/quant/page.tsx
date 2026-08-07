'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line,
} from 'recharts';
import { useAuth } from '../../lib/auth-context';
import {
  apiOptimize, apiRisk, apiBacktest, apiFactorModel,
  sampleReturns, sampleReturnMatrix, sampleFactorMatrix,
  pct, fmt,
  OptimizeResult, RiskResult, BacktestResult, FactorResult,
} from '../../lib/api';

export default function QuantPage() {
  const { token, loading } = useAuth();
  const router = useRouter();

  const [optResult, setOptResult] = useState<OptimizeResult | null>(null);
  const [riskResult, setRiskResult] = useState<RiskResult | null>(null);
  const [btResult, setBtResult] = useState<BacktestResult | null>(null);
  const [factorResult, setFactorResult] = useState<FactorResult | null>(null);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!loading && !token) router.replace('/');
  }, [token, loading, router]);

  if (loading || !token) return null;

  async function run<T>(key: string, fn: () => Promise<T>, set: (v: T) => void) {
    setBusy(key);
    setError('');
    try {
      set(await fn());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setBusy(null);
    }
  }

  const handleOptimize = () =>
    run('optimize', () =>
      apiOptimize(
        token,
        [0.05, 0.07, 0.06, 0.08],
        [
          [0.01,  0.002,  0.001, 0.0005],
          [0.002, 0.015,  0.003, 0.001],
          [0.001, 0.003,  0.012, 0.002],
          [0.0005,0.001,  0.002, 0.009],
        ],
        0.02,
      ), setOptResult,
    );

  const handleRisk = () =>
    run('risk', () => apiRisk(token, sampleReturns(500), 0.95), setRiskResult);

  const handleBacktest = () =>
    run('backtest', () =>
      apiBacktest(token, sampleReturnMatrix(252, 4), [0.4, 0.3, 0.2, 0.1]),
      setBtResult,
    );

  const handleFactor = () =>
    run('factor', () =>
      apiFactorModel(
        token,
        sampleReturns(252),
        sampleFactorMatrix(252, 3),
        ['Market', 'Size (SMB)', 'Value (HML)'],
      ), setFactorResult,
    );

  const weightData = optResult
    ? optResult.weights.map((w, i) => ({ asset: `Asset ${i + 1}`, weight: parseFloat((w * 100).toFixed(2)) }))
    : [];

  const equityData = btResult
    ? btResult.equity.map((v, i) => ({ day: i + 1, equity: parseFloat(v.toFixed(4)) }))
    : [];

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Quant Lab</div>
        <div className="page-subtitle">
          Portfolio optimization · Risk metrics · Backtesting · Factor attribution
        </div>
      </div>

      {error && <div className="alert alert-bad" style={{ marginBottom: 20 }}>{error}</div>}

      <div className="stack">

        {/* ── Portfolio Optimization ── */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Portfolio Optimization</div>
              <div className="text-muted" style={{ fontSize: 13 }}>
                Markowitz mean-variance (4 assets, R<sub>f</sub> = 2%)
              </div>
            </div>
            <button onClick={handleOptimize} disabled={busy !== null}>
              {busy === 'optimize' ? <><span className="spinner" />Running…</> : 'Run Optimizer'}
            </button>
          </div>

          {optResult && (
            <div className="grid-2">
              <div>
                <div className="card-title">Weights</div>
                <table style={{ marginTop: 8 }}>
                  <thead><tr><th>Asset</th><th>Weight</th><th>Allocation</th></tr></thead>
                  <tbody>
                    {optResult.weights.map((w, i) => (
                      <tr key={i}>
                        <td>Asset {i + 1}</td>
                        <td className={w >= 0 ? 'text-ok' : 'text-bad'}>{pct(w)}</td>
                        <td>
                          <div style={{ background: 'var(--border)', borderRadius: 4, height: 6, width: '100%' }}>
                            <div style={{ background: w >= 0 ? 'var(--ok)' : 'var(--bad)', borderRadius: 4, height: '100%', width: `${Math.min(Math.abs(w) * 100, 100)}%` }} />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div>
                <div className="card-title">Weight Distribution</div>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={weightData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                    <CartesianGrid stroke="#1e2d4a" vertical={false} />
                    <XAxis dataKey="asset" tick={{ fontSize: 11 }} stroke="#4e6485" tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 11 }} stroke="#4e6485" tickLine={false} axisLine={false} unit="%" />
                    <Tooltip contentStyle={{ background: '#0e1628', border: '1px solid #1e2d4a', borderRadius: 8, fontSize: 12 }} formatter={(v) => [typeof v === 'number' ? `${v.toFixed(2)}%` : v, 'Weight']} />
                    <Bar dataKey="weight" fill="#4f8ef7" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>

        {/* ── Risk Metrics ── */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Risk Metrics</div>
              <div className="text-muted" style={{ fontSize: 13 }}>Historical VaR · CVaR · Annualised Volatility (500 periods)</div>
            </div>
            <button onClick={handleRisk} disabled={busy !== null}>
              {busy === 'risk' ? <><span className="spinner" />Running…</> : 'Compute Risk'}
            </button>
          </div>

          {riskResult && (
            <div className="grid-3">
              {[
                { label: 'Historical VaR (95%)', value: pct(riskResult.historical_var), variant: 'card-bad' },
                { label: 'CVaR / Expected Shortfall', value: pct(riskResult.cvar), variant: 'card-bad' },
                { label: 'Ann. Volatility', value: pct(riskResult.volatility_annual), variant: 'card-warn' },
              ].map((m) => (
                <div key={m.label} className={`card ${m.variant}`} style={{ background: 'var(--surface2)' }}>
                  <div className="card-title">{m.label}</div>
                  <div className="card-value" style={{ fontSize: 22 }}>{m.value}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Backtest ── */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Strategy Backtest</div>
              <div className="text-muted" style={{ fontSize: 13 }}>Equity curve · 4-asset 40/30/20/10 allocation · 252 periods</div>
            </div>
            <button onClick={handleBacktest} disabled={busy !== null}>
              {busy === 'backtest' ? <><span className="spinner" />Running…</> : 'Run Backtest'}
            </button>
          </div>

          {btResult && (
            <>
              <div className="grid-4" style={{ marginBottom: 20 }}>
                {[
                  { label: 'Total Return', value: pct(btResult.total_return), ok: btResult.total_return >= 0 },
                  { label: 'Ann. Return', value: pct(btResult.annualised_return), ok: btResult.annualised_return >= 0 },
                  { label: 'Sharpe Ratio', value: fmt(btResult.sharpe_ratio, 3), ok: btResult.sharpe_ratio >= 0 },
                  { label: 'Max Drawdown', value: pct(btResult.max_drawdown), ok: false },
                ].map((m) => (
                  <div key={m.label} className="card" style={{ background: 'var(--surface2)', borderTop: `2px solid ${m.ok ? 'var(--ok)' : 'var(--bad)'}` }}>
                    <div className="card-title">{m.label}</div>
                    <div className="card-value" style={{ fontSize: 20, color: m.ok ? 'var(--ok)' : 'var(--bad)' }}>{m.value}</div>
                  </div>
                ))}
              </div>
              <div className="card-title" style={{ marginBottom: 8 }}>Equity Curve</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={equityData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#1e2d4a" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="day" stroke="#4e6485" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis stroke="#4e6485" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(v) => v.toFixed(2)} />
                  <Tooltip contentStyle={{ background: '#0e1628', border: '1px solid #1e2d4a', borderRadius: 8, fontSize: 12 }} formatter={(v) => [typeof v === 'number' ? v.toFixed(4) : v, 'Equity']} labelFormatter={(l) => `Day ${l}`} />
                  <Line type="monotone" dataKey="equity" stroke="#34d48a" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </>
          )}
        </div>

        {/* ── Factor Model ── */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Factor Attribution (OLS)</div>
              <div className="text-muted" style={{ fontSize: 13 }}>Fama-French style · Market, Size (SMB), Value (HML) · 252 periods</div>
            </div>
            <button onClick={handleFactor} disabled={busy !== null}>
              {busy === 'factor' ? <><span className="spinner" />Running…</> : 'Run Factor Model'}
            </button>
          </div>

          {factorResult && (
            <div className="grid-2">
              <div>
                <table>
                  <thead><tr><th>Metric</th><th>Value</th></tr></thead>
                  <tbody>
                    <tr><td>Alpha (period)</td><td className="text-accent">{fmt(factorResult.alpha, 6)}</td></tr>
                    <tr><td>Alpha (annualised)</td><td className="text-accent">{pct(factorResult.annualised_alpha)}</td></tr>
                    <tr><td>R²</td><td>{fmt(factorResult.r_squared, 4)}</td></tr>
                    <tr><td>Residual Vol</td><td>{pct(factorResult.residual_volatility)}</td></tr>
                    {factorResult.betas.map((b, i) => (
                      <tr key={i}>
                        <td>β {factorResult.factor_names[i]}</td>
                        <td className={b >= 0 ? 'text-ok' : 'text-bad'}>{fmt(b, 4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div>
                <div className="card-title" style={{ marginBottom: 8 }}>Factor Betas</div>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart
                    data={factorResult.betas.map((b, i) => ({ name: factorResult.factor_names[i], beta: parseFloat(b.toFixed(4)) }))}
                    margin={{ top: 4, right: 4, bottom: 0, left: -20 }}
                  >
                    <CartesianGrid stroke="#1e2d4a" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} stroke="#4e6485" tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 11 }} stroke="#4e6485" tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ background: '#0e1628', border: '1px solid #1e2d4a', borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="beta" fill="#7b5cf0" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
