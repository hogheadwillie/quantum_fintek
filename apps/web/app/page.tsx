'use client';

import { FormEvent, useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TOKEN_KEY = 'qf_access_token';

export default function HomePage() {
  const [token, setToken] = useState<string>('');
  const [email, setEmail] = useState('analyst@quantumfintek.local');
  const [username, setUsername] = useState('analyst');
  const [password, setPassword] = useState('changeme123');
  const [me, setMe] = useState<string>('');
  const [quant, setQuant] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [info, setInfo] = useState<string>('');

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
    setQuant('');
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
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setInfo(`Registered ${data.username}. You can log in.`);
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
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      saveToken(data.access_token);
      setInfo('Logged in.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  async function loadMe() {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
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
      const res = await fetch(`${API_URL}/quant/optimize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
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
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setQuant(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Optimize failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <span className="badge">v0.4.0-alpha</span>
      <h1>QuantumFintek</h1>
      <p>
        Enterprise quantitative finance console. API:{' '}
        <code>{API_URL}</code>
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
        <div className="card">
          <strong>Session</strong>
          <p className="ok">Authenticated</p>
          <div className="row">
            <button onClick={loadMe} disabled={loading}>
              GET /auth/me
            </button>
            <button onClick={runOptimize} disabled={loading}>
              POST /quant/optimize
            </button>
            <button className="secondary" onClick={logout} disabled={loading}>
              Logout
            </button>
          </div>
          {me && (
            <>
              <p className="ok">Profile</p>
              <pre>{me}</pre>
            </>
          )}
          {quant && (
            <>
              <p className="ok">Portfolio weights</p>
              <pre>{quant}</pre>
            </>
          )}
        </div>
      )}

      {info && <p className="ok">{info}</p>}
      {error && <p className="bad">{error}</p>}
    </main>
  );
}
