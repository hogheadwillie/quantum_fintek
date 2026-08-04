'use client';

import { FormEvent, useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TOKEN_KEY = 'qf_access_token';

function sampleReturns(n = 252): number[] {
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    out.push(0.0005 + (Math.random() - 0.48) * 0.02);
  }
  return out;
}

function sampleMatrix(rows = 40, cols = 4): number[][] {
  return Array.from({ length: rows }, () =>
    Array.from({ length: cols }, () => (Math.random() - 0.5) * 2),
  );
}

type OptimizeResult = { weights: number[]; n_assets: number };
type RiskResult = { historical_var: number; cvar: number; volatility_annual: number };
type AnomalyResult = { labels: number[]; scores: number[]; n_anomalies: number };

export default function HomePage() {
  const [token, setToken] = useState('');
  const [email, setEmail] = useState('analyst@quantumfintek.local');
  const [username, setUsername] = useState('analyst');
  const [password, setPassword] = useState('changeme123');
  const [me, setMe] = useState('');
  const [quant, setQuant] = useState<OptimizeResult | null>(null);
  const [risk, setRisk] = useState<RiskResult | null>(null);
  const [anomaly, setAnomaly] = useState<AnomalyResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  useEffect(() => {
    const saved = localStorage.getItem(TOKEN_KEY);
    if (saved) setToken(saved);
  }, []);

  function saveToken(t: string) {
    setToken(t);
    localStorage.setItem(TOKEN_KEY, t);
  }

  function logout() {
    setToken('');
    setMe('');
    setQuant(null);
    setRisk(null);
    setAnomaly(null);
    localStorage.removeItem(TOKEN_KEY);
  }

  async function register(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setInfo('');
    try {
      const res = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, username, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${res.status}`);
      setInfo(`Registered ${data.username} (org ${data.org_id || 'created'}). Log in.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Register failed');
    } finally {
      setLoading(false);
    }
  }

  async function login(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setInfo('');
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${res.status}`);
      saveToken(data.access_token);
      setInfo('Logged in.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  async function authFetch(path: string, init?: RequestInit) {
    const res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(init?.headers || {}),
      },
    });
    const data = await res.json();
    if (!res.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      throw new Error(detail || `HTTP ${res.status}`);
    }
    return data;
  }

  async function loadMe() {
    setLoading(true);
    setError('');
    try {
      const data = await authFetch('/auth/me');
      setMe(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  }

  async function runOptimize() {
    setLoading(true);
    setError('');
    try {
      const data = await authFetch('/quant/optimize', {
        method: 'POST',
        body: JSON.stringify({
          expected_returns: [0.05, 0.07, 0.06],
          covariance: [
            [0.01, 0.002, 0.001],
            [0.002, 0.015, 0.003],
            [0.001, 0.003, 0.012],
          ],
          risk_free_rate: 0.02,
        }),
      });
      setQuant(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Optimize failed');
    } finally {
      setLoading(false);
    }
  }

  async function runRisk() {
    setLoading(true);
    setError('');
    try {
      const data = await authFetch('/quant/risk', {
        method: 'POST',
        body: JSON.stringify({ returns: sampleReturns(), confidence: 0.95 }),
      });
      setRisk(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Risk failed');
    } finally {
      setLoading(false);
    }
  }

  async function runAnomaly() {
    setLoading(true);
    setError('');
    try {
      const data = await authFetch('/ai/anomaly', {
        method: 'POST',
        body: JSON.stringify({ samples: sampleMatrix(), contamination: 0.08 }),
      });
      setAnomaly(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Anomaly failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <span className="badge">v0.6.0-alpha</span>
      <h1>QuantumFintek</h1>
      <p>
        Enterprise quantitative finance console. API: <code>{API_URL}</code>
      </p>

      {!token ? (
        <div className="card">
          <strong>Sign in</strong>
          <form className="form" onSubmit={login}>
            <label>
              Email
              <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
            </label>
            <label>
              Username <span className="hint">(register only)</span>
              <input value={username} onChange={(e) => setUsername(e.target.value)} />
            </label>
            <label>
              Password
              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type="password"
                required
                minLength={8}
              />
            </label>
            <div className="row">
              <button type="submit" disabled={loading}>
                Login
              </button>
              <button type="button" className="secondary" onClick={register} disabled={loading}>
                Register
              </button>
            </div>
          </form>
        </div>
      ) : (
        <>
          <div className="card">
            <strong>Session</strong>
            <p className="ok">Authenticated</p>
            <div className="row">
              <button onClick={loadMe} disabled={loading}>
                Profile
              </button>
              <button className="secondary" onClick={logout} disabled={loading}>
                Logout
              </button>
            </div>
            {me && <pre>{me}</pre>}
          </div>

          <div className="card">
            <strong>Quant lab</strong>
            <div className="row">
              <button onClick={runOptimize} disabled={loading}>
                Optimize portfolio
              </button>
              <button onClick={runRisk} disabled={loading}>
                Risk (VaR / CVaR)
              </button>
            </div>

            {quant && (
              <div className="viz">
                <p className="ok">Portfolio weights</p>
                {quant.weights.map((w, i) => (
                  <div className="bar-row" key={i}>
                    <span className="bar-label">Asset {i + 1}</span>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${Math.max(0, Math.min(100, w * 100))}%` }} />
                    </div>
                    <span className="bar-value">{(w * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            )}

            {risk && (
              <div className="metrics">
                <div className="metric">
                  <span className="metric-label">Hist. VaR</span>
                  <span className="metric-value">{risk.historical_var.toFixed(4)}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">CVaR</span>
                  <span className="metric-value">{risk.cvar.toFixed(4)}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Ann. vol</span>
                  <span className="metric-value">{(risk.volatility_annual * 100).toFixed(1)}%</span>
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <strong>AI intelligence</strong>
            <div className="row">
              <button onClick={runAnomaly} disabled={loading}>
                Anomaly detection
              </button>
            </div>
            {anomaly && (
              <div className="metrics">
                <div className="metric">
                  <span className="metric-label">Samples</span>
                  <span className="metric-value">{anomaly.labels.length}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Anomalies</span>
                  <span className="metric-value bad">{anomaly.n_anomalies}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Rate</span>
                  <span className="metric-value">
                    {((anomaly.n_anomalies / Math.max(1, anomaly.labels.length)) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {info && <p className="ok">{info}</p>}
      {error && <p className="bad">{error}</p>}
    </main>
  );
}
