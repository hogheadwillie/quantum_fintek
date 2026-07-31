'use client';

import { useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function HomePage() {
  const [health, setHealth] = useState<string>('');
  const [quant, setQuant] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  async function checkHealth() {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/health`);
      const data = await res.json();
      setHealth(JSON.stringify(data, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Health check failed');
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
        headers: { 'Content-Type': 'application/json' },
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
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setQuant(JSON.stringify(data, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Optimize failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <span className="badge">v0.3.0-alpha</span>
      <h1>QuantumFintek</h1>
      <p>
        Enterprise quantitative finance console. API base:{' '}
        <code>{API_URL}</code>
      </p>

      <div className="card">
        <strong>Connectivity</strong>
        <div className="row">
          <button onClick={checkHealth} disabled={loading}>
            GET /health
          </button>
          <button onClick={runOptimize} disabled={loading}>
            POST /quant/optimize
          </button>
        </div>
        {error && <p className="bad">{error}</p>}
        {health && (
          <>
            <p className="ok">Health</p>
            <pre>{health}</pre>
          </>
        )}
        {quant && (
          <>
            <p className="ok">Portfolio weights</p>
            <pre>{quant}</pre>
          </>
        )}
      </div>
    </main>
  );
}
