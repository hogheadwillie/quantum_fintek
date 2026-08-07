'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../lib/auth-context';
import { apiMe } from '../../lib/api';

export default function ProfilePage() {
  const { token, user, loading, logout } = useAuth();
  const router = useRouter();
  const [refreshed, setRefreshed] = useState(false);

  useEffect(() => {
    if (!loading && !token) router.replace('/');
  }, [token, loading, router]);

  useEffect(() => {
    if (token && !refreshed) {
      apiMe(token).then(() => setRefreshed(true)).catch(() => {});
    }
  }, [token, refreshed]);

  if (loading || !token || !user) return null;

  const initials = user.username.slice(0, 2).toUpperCase();
  const joinDate = '2024'; // placeholder — not in current API response

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Profile</div>
        <div className="page-subtitle">Account details and session management</div>
      </div>

      <div className="grid-2">

        {/* Identity card */}
        <div className="card card-accent">
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
            <div
              style={{
                width: 56,
                height: 56,
                background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%)',
                borderRadius: '50%',
                display: 'grid',
                placeItems: 'center',
                fontWeight: 700,
                fontSize: 20,
                color: '#fff',
                flexShrink: 0,
              }}
            >
              {initials}
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 18 }}>{user.username}</div>
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>{user.email}</div>
            </div>
          </div>

          <table>
            <tbody>
              <tr><td style={{ color: 'var(--subtle)', width: 100 }}>User ID</td><td><code style={{ fontSize: 11 }}>{user.id}</code></td></tr>
              <tr><td style={{ color: 'var(--subtle)' }}>Status</td><td><span className="badge badge-ok">{user.status}</span></td></tr>
              <tr>
                <td style={{ color: 'var(--subtle)' }}>Roles</td>
                <td>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {user.roles.map((r) => (
                      <span key={r} className="badge badge-accent">{r}</span>
                    ))}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Session management */}
        <div className="card">
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>Session</div>

          <div className="stack" style={{ gap: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', background: 'var(--surface2)', borderRadius: 8, border: '1px solid var(--border)' }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>Current session</div>
                <div style={{ fontSize: 12, color: 'var(--subtle)' }}>Bearer JWT · analyst RBAC</div>
              </div>
              <span className="badge badge-ok">Active</span>
            </div>

            <div style={{ fontSize: 12.5, color: 'var(--muted)', padding: '8px 0' }}>
              Your access token expires in 30 minutes and rotates automatically via refresh tokens stored in Redis.
            </div>

            <button className="danger" onClick={() => { logout(); router.replace('/'); }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
              Sign Out
            </button>
          </div>
        </div>

        {/* Platform capabilities */}
        <div className="card col-span-2">
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>Available Capabilities</div>
          <div className="grid-3">
            {[
              { title: 'Portfolio Optimization', desc: 'Markowitz mean-variance with quantum-ready QUBO export', href: '/quant', color: 'var(--accent)' },
              { title: 'Risk Analytics', desc: 'Historical VaR, CVaR, annualised volatility over arbitrary return series', href: '/quant', color: 'var(--warn)' },
              { title: 'Strategy Backtest', desc: 'Vectorised equity-curve engine: Sharpe, drawdown, CAGR', href: '/quant', color: 'var(--ok)' },
              { title: 'Factor Attribution', desc: 'OLS regression: alpha, betas, R², t-stats vs. Fama-French factors', href: '/quant', color: 'var(--accent2)' },
              { title: 'Anomaly Detection', desc: 'Isolation Forest on arbitrary feature matrices, calibratable contamination', href: '/ai', color: 'var(--bad)' },
              { title: 'Sentiment Analysis', desc: 'Financial lexicon NLP: negation-aware scoring, per-document confidence', href: '/ai', color: 'var(--ok)' },
            ].map((c) => (
              <a
                key={c.title}
                href={c.href}
                style={{ textDecoration: 'none', display: 'block', padding: '14px 16px', background: 'var(--surface2)', borderRadius: 10, border: '1px solid var(--border)', borderTop: `2px solid ${c.color}` }}
              >
                <div style={{ fontWeight: 600, fontSize: 13.5, marginBottom: 4 }}>{c.title}</div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>{c.desc}</div>
              </a>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
