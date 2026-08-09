'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { useAuth } from '../../lib/auth-context';
import { apiAdminAudit, apiAdminUsers, AuditListResponse, UserListResponse } from '../../lib/api';

export default function AdminPage() {
  const { token, user, loading } = useAuth();
  const router = useRouter();

  const [auditData, setAuditData] = useState<AuditListResponse | null>(null);
  const [usersData, setUsersData] = useState<UserListResponse | null>(null);
  const [tab, setTab] = useState<'audit' | 'users'>('audit');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!loading && !token) router.replace('/');
  }, [token, loading, router]);

  useEffect(() => {
    if (!token) return;
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function loadAll() {
    if (!token) return;
    setBusy(true);
    setError('');
    try {
      const [a, u] = await Promise.all([
        apiAdminAudit(token),
        apiAdminUsers(token),
      ]);
      setAuditData(a);
      setUsersData(u);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load admin data');
    } finally {
      setBusy(false);
    }
  }

  if (loading || !token) return null;

  const isAdmin = user?.roles.some((r) => ['admin', 'owner'].includes(r));

  if (!isAdmin) {
    return (
      <div className="page">
        <div className="page-header">
          <div className="page-title">Admin Console</div>
        </div>
        <div className="alert alert-bad">
          Access denied — requires <strong>admin</strong> or <strong>owner</strong> role.
        </div>
      </div>
    );
  }

  // Summarise audit actions for bar chart
  const actionCounts: Record<string, number> = {};
  auditData?.events.forEach((e) => {
    const key = e.action.split('.').slice(0, 2).join('.');
    actionCounts[key] = (actionCounts[key] || 0) + 1;
  });
  const chartData = Object.entries(actionCounts).map(([action, count]) => ({ action, count }));

  return (
    <div className="page">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div className="page-title">Admin Console</div>
            <div className="page-subtitle">
              Audit log · User management · {auditData?.total ?? 0} events · {usersData?.total ?? 0} users
            </div>
          </div>
          <button className="secondary" onClick={loadAll} disabled={busy}>
            {busy ? <><span className="spinner" />Loading…</> : (
              <><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.91"/></svg>Refresh</>
            )}
          </button>
        </div>
      </div>

      {error && <div className="alert alert-bad" style={{ marginBottom: 20 }}>{error}</div>}

      {/* Summary KPIs */}
      <div className="grid-4" style={{ marginBottom: 24 }}>
        {[
          { label: 'Total Events', value: auditData?.total ?? '—', variant: 'card-accent' },
          { label: 'Total Users', value: usersData?.total ?? '—', variant: 'card-ok' },
          { label: 'Active Users', value: usersData?.users.filter((u) => u.status === 'active').length ?? '—', variant: 'card-ok' },
          { label: 'Action Types', value: chartData.length, variant: 'card-warn' },
        ].map((m) => (
          <div key={m.label} className={`card ${m.variant}`}>
            <div className="card-title">{m.label}</div>
            <div className="card-value">{m.value}</div>
          </div>
        ))}
      </div>

      {/* Action distribution chart */}
      {chartData.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>Event Distribution</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
              <CartesianGrid stroke="#1e2d4a" vertical={false} />
              <XAxis dataKey="action" tick={{ fontSize: 10 }} stroke="#4e6485" tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 11 }} stroke="#4e6485" tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: '#0e1628', border: '1px solid #1e2d4a', borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="count" fill="#7b5cf0" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {(['audit', 'users'] as const).map((t) => (
          <button
            key={t}
            className={tab === t ? '' : 'secondary'}
            onClick={() => setTab(t)}
            style={{ minWidth: 100, textTransform: 'capitalize' }}
          >
            {t === 'audit' ? `Audit Log (${auditData?.total ?? 0})` : `Users (${usersData?.total ?? 0})`}
          </button>
        ))}
      </div>

      {/* Audit log table */}
      {tab === 'audit' && auditData && (
        <div className="card">
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>Actor</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {auditData.events.map((e) => (
                  <tr key={e.id}>
                    <td className="text-muted" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                    <td>
                      <span className="badge badge-accent" style={{ fontFamily: 'monospace', fontSize: 11 }}>
                        {e.action}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, fontFamily: 'monospace', color: 'var(--muted)' }}>{e.resource}</td>
                    <td style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--subtle)' }}>
                      {e.actor_id ? e.actor_id.slice(0, 8) + '…' : '—'}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--muted)', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {e.detail}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Users table */}
      {tab === 'users' && usersData && (
        <div className="card">
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Status</th>
                  <th>Joined</th>
                  <th>Last Login</th>
                </tr>
              </thead>
              <tbody>
                {usersData.users.map((u) => (
                  <tr key={u.id}>
                    <td style={{ fontWeight: 600 }}>{u.username}</td>
                    <td style={{ fontSize: 13, color: 'var(--muted)' }}>{u.email}</td>
                    <td>
                      <span className={`badge badge-${u.status === 'active' ? 'ok' : 'bad'}`}>{u.status}</span>
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--subtle)' }}>
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--subtle)' }}>
                      {u.last_login ? new Date(u.last_login).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
