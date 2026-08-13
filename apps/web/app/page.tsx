'use client';

import { FormEvent, useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TOKEN_KEY = 'qf_access_token';
const REFRESH_KEY = 'qf_refresh_token';

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

/** Extract a readable error from FastAPI responses (string or validation list). */
function parseApiError(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') return fallback;
  const d = data as Record<string, unknown>;
  if (typeof d.detail === 'string') return d.detail;
  if (Array.isArray(d.detail)) {
    return d.detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          const obj = item as Record<string, unknown>;
          const loc = Array.isArray(obj.loc) ? obj.loc.slice(1).join('.') : '';
          const msg = typeof obj.msg === 'string' ? obj.msg : JSON.stringify(obj);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return String(item);
      })
      .join('; ');
  }
  if (d.detail !== undefined) return JSON.stringify(d.detail);
  return fallback;
}

type OptimizeResult = { weights: number[]; n_assets: number };
type RiskResult = { historical_var: number; cvar: number; volatility_annual: number };
type AnomalyResult = { labels: number[]; scores: number[]; n_anomalies: number };

export default function HomePage() {
  const [token, setToken] = useState('');
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
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

  function saveTokens(access: string, refresh?: string) {
    setToken(access);
    localStorage.setItem(TOKEN_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  }

  function logout() {
    setToken('');
    setMe('');
    setQuant(null);
    setRisk(null);
    setAnomaly(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  }

  function switchMode(next: 'login' | 'register') {
    setMode(next);
    setError('');
    setInfo('');
    setConfirmPassword('');
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setInfo('');

    try {
      if (mode === 'register') {
        if (password.length < 8) {
          throw new Error('Password must be at least 8 characters');\n        }
        if (password !== confirmPassword) {
          throw new Error('Passwords do not match');
        }
        if (!username.trim()) {
          throw new Error('Username is required');
        }

        // Register
        const regRes = await fetch(`${API_URL}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: email.trim(),
            username: username.trim(),
            password,
          }),
        });
        const regData = await regRes.json();
        if (!regRes.ok) {
          throw new Error(parseApiError(regData, `Register failed (HTTP ${regRes.status})`));
        }

        // Auto-login after successful registration
        const loginRes = await fetch(`${API_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email.trim(), password }),
        });
        const loginData = await loginRes.json();
        if (!loginRes.ok) {
          setInfo(`Account created for ${regData.username}. Please log in.`);
          setMode('login');
          return;
        }

        saveTokens(loginData.access_token, loginData.refresh_token);
        setInfo(`Welcome, ${regData.username}! Account created and signed in.`);
      } else {
        // Login
        const res = await fetch(`${API_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email.trim(), password }),
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(parseApiError(data, `Login failed (HTTP ${res.status})`));
        }
        saveTokens(data.access_token, data.refresh_token);
        setInfo('Signed in successfully.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
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
      throw new Error(parseApiError(data, `HTTP ${res.status}`));
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
      <span className="badge">v0.8.0-alpha</span>
      <h1>QuantumFintek</h1>
      <p>
        Enterprise quantitative finance console. API: <code>{API_URL}</code>
      </p>

      {!token ? (
        <div className="card">
          <div className="row" style={{ marginBottom: '1rem', gap: '0.5rem' }}>
            <button
              type="button"
              className={mode === 'login' ? '' : 'secondary'}
              onClick={() => switchMode('login')}
              disabled={loading}
            >
              Sign in
            </button>
            <button
              type="button"
              className={mode === 'register' ? '' : 'secondary'}
              onClick={() => switchMode('register')}
              disabled={loading}
            >
              Create account
            </button>
          </div>

          <strong>{mode === 'login' ? 'Sign in' : 'Create account'}</strong>

          <form className="form" onSubmit={handleSubmit}>
            <label>
              Email
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                type="email"
                autoComplete="email"
                required
                placeholder="you@company.com"
              />
            </label>

            {mode === 'register' && (
              <label>
                Username
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  required
                  minLength={2}
                  placeholder="analyst"
                />
              </label>
            )}

            <label>
              Password
              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                required
                minLength={8}
                placeholder="Min. 8 characters"
              />
            </label>

            {mode === 'register' && (
              <label>
                Confirm password
                <input
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  placeholder="Repeat password"
                />
              </label>
            )}

            <div className="row">
              <button type="submit" disabled={loading}>
                {loading
                  ? mode === 'login'
                    ? 'Signing in…'
                    : 'Creating account…'
                  : mode === 'login'
                    ? 'Sign in'
                    : 'Create account'}
              </button>
            </div>
          </form>

          <p className="hint" style={{ marginTop: '0.75rem', fontSize: '0.85rem' }}>
            {mode === 'login' ? (
              <>
                No account?{' '}
                <button type="button" className="link" onClick={() => switchMode('register')}>
                  Create one
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button type="button" className="link" onClick={() => switchMode('login')}>
                  Sign in
                </button>
              </>
            )}
          </p>
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
                      <div
                        className="bar-fill"
                        style={{ width: `${Math.max(0, Math.min(100, w * 100))}%` }}
                      />
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
