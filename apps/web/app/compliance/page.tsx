'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../lib/auth-context';
import {
  apiCompliance, apiMarketData,
  ComplianceResponse, MarketDataResponse,
} from '../../lib/api';

const CONTROL_STATUS_COLOR: Record<string, string> = {
  implemented: 'badge-ok',
  partial: 'badge-warn',
  planned: 'badge-neutral',
  not_applicable: 'badge-neutral',
};

export default function CompliancePage() {
  const { token, user, loading } = useAuth();
  const router = useRouter();

  const [data, setData] = useState<ComplianceResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!loading && !token) router.replace('/');
  }, [token, loading, router]);

  useEffect(() => {
    if (!token) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function load() {
    if (!token) return;
    setBusy(true);
    setError('');
    try {
      setData(await apiCompliance(token));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load compliance data');
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
          <div className="page-title">Compliance</div>
        </div>
        <div className="alert alert-bad">
          Access denied — requires <strong>admin</strong> or <strong>owner</strong> role.
        </div>
      </div>
    );
  }

  const implemented = data?.items.filter((i) => i.status === 'implemented').length ?? 0;
  const partial = data?.items.filter((i) => i.status === 'partial').length ?? 0;
  const total = data?.items.length ?? 0;

  return (
    <div className="page">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div className="page-title">Compliance</div>
            <div className="page-subtitle">
              {data?.framework ?? 'CMMC L2 (subset)'} · Machine-readable evidence
            </div>
          </div>
          <button className="secondary" onClick={load} disabled={busy}>
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
          { label: 'Controls Tracked', value: total, variant: 'card-accent' },
          { label: 'Implemented', value: implemented, variant: 'card-ok' },
          { label: 'Partial', value: partial, variant: 'card-warn' },
          { label: 'Audit Events', value: data?.audit_event_count ?? '—', variant: 'card-accent' },
        ].map((m) => (
          <div key={m.label} className={`card ${m.variant}`}>
            <div className="card-title">{m.label}</div>
            <div className="card-value">{busy ? <span className="spinner" /> : m.value}</div>
          </div>
        ))}
      </div>

      {/* Progress bar */}
      {total > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span className="card-title">Coverage</span>
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>
              {Math.round(((implemented + partial * 0.5) / total) * 100)}% effective
            </span>
          </div>
          <div style={{ background: 'var(--border)', borderRadius: 6, height: 8, overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${Math.round(((implemented + partial * 0.5) / total) * 100)}%`,
                background: 'linear-gradient(90deg, var(--ok), var(--accent))',
                borderRadius: 6,
                transition: 'width 0.4s ease',
              }}
            />
          </div>
          <div style={{ display: 'flex', gap: 20, marginTop: 10, fontSize: 12 }}>
            {[
              { label: 'Implemented', color: 'var(--ok)' },
              { label: 'Partial', color: 'var(--warn)' },
              { label: 'Planned', color: 'var(--subtle)' },
            ].map((l) => (
              <span key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--muted)' }}>
                <span style={{ width: 10, height: 10, background: l.color, borderRadius: 2, display: 'inline-block' }} />
                {l.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Evidence table */}
      {data && (
        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>Control Evidence</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {data.items.map((item) => (
              <div
                key={item.control}
                style={{
                  padding: '14px 16px',
                  background: 'var(--surface2)',
                  borderRadius: 10,
                  border: '1px solid var(--border)',
                  borderLeft: `3px solid ${item.status === 'implemented' ? 'var(--ok)' : item.status === 'partial' ? 'var(--warn)' : 'var(--subtle)'}`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                  <div>
                    <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--accent)', marginRight: 10 }}>
                      {item.control}
                    </span>
                    <span style={{ fontWeight: 600, fontSize: 14 }}>{item.title}</span>
                  </div>
                  <span className={`badge ${CONTROL_STATUS_COLOR[item.status] ?? 'badge-neutral'}`}>
                    {item.status}
                  </span>
                </div>
                <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 4 }}>{item.evidence}</div>
                <div style={{ fontSize: 11, color: 'var(--subtle)' }}>
                  Collected {new Date(item.collected_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
