'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../lib/auth-context';
import {
  apiCompliance, apiZosCompliance, apiZosAuditLog,
  ComplianceResponse, MainframeEvidenceResponse, MainframeAuditListResponse,
} from '../../lib/api';

const CONTROL_STATUS_COLOR: Record<string, string> = {
  implemented:    'badge-ok',
  partial:        'badge-warn',
  planned:        'badge-neutral',
  not_applicable: 'badge-neutral',
};

const OUTCOME_COLOR: Record<string, string> = {
  success: 'var(--ok)',
  denied:  'var(--danger)',
  error:   'var(--warn)',
};

type ActiveTab = 'cmmc' | 'zos' | 'audit';

export default function CompliancePage() {
  const { token, user, loading } = useAuth();
  const router = useRouter();

  const [tab, setTab] = useState<ActiveTab>('cmmc');

  // CMMC state
  const [data, setData]     = useState<ComplianceResponse | null>(null);
  const [busyCmmc, setBusyCmmc] = useState(false);
  const [errorCmmc, setErrorCmmc] = useState('');

  // z/OS compliance state
  const [zosData, setZosData]     = useState<MainframeEvidenceResponse | null>(null);
  const [busyZos, setBusyZos]     = useState(false);
  const [errorZos, setErrorZos]   = useState('');

  // Mainframe audit log state
  const [auditData, setAuditData]   = useState<MainframeAuditListResponse | null>(null);
  const [busyAudit, setBusyAudit]   = useState(false);
  const [errorAudit, setErrorAudit] = useState('');
  const [auditFilter, setAuditFilter] = useState('');
  const [auditLpar, setAuditLpar]     = useState('');

  useEffect(() => {
    if (!loading && !token) router.replace('/');
  }, [token, loading, router]);

  useEffect(() => {
    if (!token) return;
    loadCmmc();
    loadZos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function loadCmmc() {
    if (!token) return;
    setBusyCmmc(true);
    setErrorCmmc('');
    try { setData(await apiCompliance(token)); }
    catch (err) { setErrorCmmc(err instanceof Error ? err.message : 'Failed'); }
    finally { setBusyCmmc(false); }
  }

  async function loadZos() {
    if (!token) return;
    setBusyZos(true);
    setErrorZos('');
    try { setZosData(await apiZosCompliance(token)); }
    catch (err) { setErrorZos(err instanceof Error ? err.message : 'Failed'); }
    finally { setBusyZos(false); }
  }

  async function loadAudit() {
    if (!token) return;
    setBusyAudit(true);
    setErrorAudit('');
    try {
      setAuditData(await apiZosAuditLog(token, {
        event_type: auditFilter || undefined,
        lpar_name:  auditLpar  || undefined,
      }));
    }
    catch (err) { setErrorAudit(err instanceof Error ? err.message : 'Failed'); }
    finally { setBusyAudit(false); }
  }

  useEffect(() => {
    if (tab === 'audit' && token && !auditData) loadAudit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, token]);

  if (loading || !token) return null;

  const isAdmin = user?.roles.some((r) => ['admin', 'owner'].includes(r));
  const canView = user?.roles.some((r) =>
    ['admin', 'owner', 'analyst', 'quant', 'trader'].includes(r)
  );

  if (!isAdmin && !canView) {
    return (
      <div className="page">
        <div className="page-header"><div className="page-title">Compliance</div></div>
        <div className="alert alert-bad">Access denied — requires admin, owner, analyst, quant, or trader role.</div>
      </div>
    );
  }

  // CMMC metrics
  const implemented = data?.items.filter((i) => i.status === 'implemented').length ?? 0;
  const partial      = data?.items.filter((i) => i.status === 'partial').length ?? 0;
  const total        = data?.items.length ?? 0;

  // z/OS metrics
  const zImpl  = zosData?.implemented_count ?? 0;
  const zPart  = zosData?.partial_count ?? 0;
  const zTotal = zosData?.total_controls ?? 0;

  const TAB_STYLE = (active: boolean): React.CSSProperties => ({
    padding: '8px 20px',
    borderRadius: 8,
    cursor: 'pointer',
    fontWeight: active ? 600 : 400,
    background: active ? 'var(--accent)' : 'transparent',
    color: active ? '#fff' : 'var(--muted)',
    border: active ? 'none' : '1px solid var(--border)',
    fontSize: 13,
  });

  return (
    <div className="page">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div className="page-title">Compliance</div>
            <div className="page-subtitle">CMMC L2 · NIST SP 800-53 · IBM z/OS Mainframe</div>
          </div>
          <button
            className="secondary"
            onClick={() => { loadCmmc(); loadZos(); if (tab === 'audit') loadAudit(); }}
            disabled={busyCmmc || busyZos}
          >
            {(busyCmmc || busyZos) ? <><span className="spinner" />Loading…</> : (
              <><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.91"/></svg>Refresh</>
            )}
          </button>
        </div>
      </div>

      {/* Cross-framework summary KPIs */}
      <div className="grid-4" style={{ marginBottom: 24 }}>
        {[
          { label: 'CMMC Controls', value: total, variant: 'card-accent' },
          { label: 'z/OS Controls',  value: zTotal, variant: 'card-accent' },
          { label: 'Implemented',    value: implemented + zImpl,  variant: 'card-ok' },
          { label: 'Partial',        value: partial + zPart, variant: 'card-warn' },
        ].map((m) => (
          <div key={m.label} className={`card ${m.variant}`}>
            <div className="card-title">{m.label}</div>
            <div className="card-value">{(busyCmmc || busyZos) ? <span className="spinner" /> : m.value}</div>
          </div>
        ))}
      </div>

      {/* Tab navigation */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        <button style={TAB_STYLE(tab === 'cmmc')}  onClick={() => setTab('cmmc')}>CMMC L2</button>
        <button style={TAB_STYLE(tab === 'zos')}   onClick={() => setTab('zos')}>IBM z/OS</button>
        {isAdmin && (
          <button style={TAB_STYLE(tab === 'audit')} onClick={() => { setTab('audit'); if (!auditData) loadAudit(); }}>
            Mainframe Audit Log
          </button>
        )}
      </div>

      {/* ── CMMC TAB ─────────────────────────────────────────────────────── */}
      {tab === 'cmmc' && (
        <>
          {errorCmmc && <div className="alert alert-bad" style={{ marginBottom: 20 }}>{errorCmmc}</div>}
          {total > 0 && (
            <div className="card" style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span className="card-title">CMMC Coverage</span>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                  {Math.round(((implemented + partial * 0.5) / total) * 100)}% effective
                </span>
              </div>
              <div style={{ background: 'var(--border)', borderRadius: 6, height: 8, overflow: 'hidden' }}>
                <div style={{
                  height: '100%',
                  width: `${Math.round(((implemented + partial * 0.5) / total) * 100)}%`,
                  background: 'linear-gradient(90deg, var(--ok), var(--accent))',
                  borderRadius: 6, transition: 'width 0.4s ease',
                }} />
              </div>
              <div style={{ display: 'flex', gap: 20, marginTop: 10, fontSize: 12 }}>
                {[{ label: 'Implemented', color: 'var(--ok)' }, { label: 'Partial', color: 'var(--warn)' }, { label: 'Planned', color: 'var(--subtle)' }].map((l) => (
                  <span key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--muted)' }}>
                    <span style={{ width: 10, height: 10, background: l.color, borderRadius: 2, display: 'inline-block' }} />
                    {l.label}
                  </span>
                ))}
              </div>
            </div>
          )}
          {data && (
            <div className="card">
              <div className="card-title" style={{ marginBottom: 16 }}>Control Evidence</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {data.items.map((item) => (
                  <div key={item.control} style={{
                    padding: '14px 16px', background: 'var(--surface2)', borderRadius: 10,
                    border: '1px solid var(--border)',
                    borderLeft: `3px solid ${item.status === 'implemented' ? 'var(--ok)' : item.status === 'partial' ? 'var(--warn)' : 'var(--subtle)'}`,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                      <div>
                        <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--accent)', marginRight: 10 }}>{item.control}</span>
                        <span style={{ fontWeight: 600, fontSize: 14 }}>{item.title}</span>
                      </div>
                      <span className={`badge ${CONTROL_STATUS_COLOR[item.status] ?? 'badge-neutral'}`}>{item.status}</span>
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 4 }}>{item.evidence}</div>
                    <div style={{ fontSize: 11, color: 'var(--subtle)' }}>Collected {new Date(item.collected_at).toLocaleString()}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── z/OS MAINFRAME TAB ───────────────────────────────────────────── */}
      {tab === 'zos' && (
        <>
          {errorZos && <div className="alert alert-bad" style={{ marginBottom: 20 }}>{errorZos}</div>}

          {/* Infrastructure summary */}
          {zosData && (
            <>
              <div className="grid-4" style={{ marginBottom: 20 }}>
                {[
                  { label: 'LPARs Online',       value: `${zosData.lpars_online}/${zosData.lpars_total}`, color: zosData.lpars_online === zosData.lpars_total ? 'var(--ok)' : 'var(--warn)' },
                  { label: 'MQ Queues Monitored', value: zosData.mq_queues_monitored, color: 'var(--accent)' },
                  { label: 'Datasets Catalogued', value: zosData.datasets_catalogued, color: 'var(--accent)' },
                  { label: 'RACF Profiles',       value: zosData.racf_profiles_active, color: 'var(--accent)' },
                ].map((m) => (
                  <div key={m.label} className="card">
                    <div className="card-title">{m.label}</div>
                    <div className="card-value" style={{ color: m.color }}>{busyZos ? <span className="spinner" /> : m.value}</div>
                  </div>
                ))}
              </div>

              {/* z/OS coverage bar */}
              {zTotal > 0 && (
                <div className="card" style={{ marginBottom: 20 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span className="card-title">z/OS Control Coverage</span>
                    <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                      {Math.round(((zImpl + zPart * 0.5) / zTotal) * 100)}% effective · {zosData.generated_at ? new Date(zosData.generated_at).toLocaleTimeString() : ''}
                    </span>
                  </div>
                  <div style={{ background: 'var(--border)', borderRadius: 6, height: 8, overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      width: `${Math.round(((zImpl + zPart * 0.5) / zTotal) * 100)}%`,
                      background: 'linear-gradient(90deg, var(--ok), var(--secondary, #7c5cd8))',
                      borderRadius: 6, transition: 'width 0.4s ease',
                    }} />
                  </div>
                </div>
              )}

              {/* Controls list */}
              <div className="card">
                <div className="card-title" style={{ marginBottom: 4 }}>Mainframe Control Evidence</div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
                  NIST SP 800-53 Rev 5 · CMMC Level 2 — evidence collected live from z/OS bridge
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {zosData.controls.map((ctrl) => (
                    <div key={ctrl.control_id} style={{
                      padding: '14px 16px', background: 'var(--surface2)', borderRadius: 10,
                      border: '1px solid var(--border)',
                      borderLeft: `3px solid ${ctrl.status === 'implemented' ? 'var(--ok)' : ctrl.status === 'partial' ? 'var(--warn)' : 'var(--subtle)'}`,
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                        <div>
                          <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--accent)', marginRight: 8 }}>{ctrl.control_id}</span>
                          <span style={{ fontWeight: 600, fontSize: 14 }}>{ctrl.title}</span>
                          <span style={{ fontSize: 11, color: 'var(--subtle)', marginLeft: 8 }}>{ctrl.family}</span>
                        </div>
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                          <span style={{ fontSize: 10, color: 'var(--muted)', padding: '2px 6px', border: '1px solid var(--border)', borderRadius: 4 }}>
                            {ctrl.framework}
                          </span>
                          <span className={`badge ${CONTROL_STATUS_COLOR[ctrl.status] ?? 'badge-neutral'}`}>{ctrl.status}</span>
                        </div>
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>{ctrl.description}</div>
                      <div style={{ fontSize: 13, color: 'var(--text)', marginBottom: 6 }}>{ctrl.evidence}</div>
                      {Object.keys(ctrl.technical_details).length > 0 && (
                        <div style={{ fontSize: 11, color: 'var(--subtle)', fontFamily: 'monospace', background: 'var(--surface)', padding: '6px 10px', borderRadius: 6 }}>
                          {Object.entries(ctrl.technical_details).map(([k, v]) => (
                            <span key={k} style={{ marginRight: 14 }}>{k}: <strong>{String(v)}</strong></span>
                          ))}
                        </div>
                      )}
                      <div style={{ fontSize: 11, color: 'var(--subtle)', marginTop: 6 }}>
                        Collected {new Date(ctrl.collected_at).toLocaleString()}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
          {busyZos && !zosData && (
            <div className="card" style={{ textAlign: 'center', padding: 40 }}>
              <span className="spinner" /> Loading mainframe compliance data…
            </div>
          )}
        </>
      )}

      {/* ── MAINFRAME AUDIT LOG TAB ──────────────────────────────────────── */}
      {tab === 'audit' && isAdmin && (
        <>
          {/* Filters */}
          <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>Event Type</div>
              <input
                value={auditFilter}
                onChange={(e) => setAuditFilter(e.target.value)}
                placeholder="e.g. racf, jcl, mq"
                style={{ width: 180 }}
                onKeyDown={(e) => e.key === 'Enter' && loadAudit()}
              />
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>LPAR</div>
              <input
                value={auditLpar}
                onChange={(e) => setAuditLpar(e.target.value.toUpperCase())}
                placeholder="e.g. SYSA"
                style={{ width: 120 }}
                onKeyDown={(e) => e.key === 'Enter' && loadAudit()}
              />
            </div>
            <button className="secondary" onClick={loadAudit} disabled={busyAudit}>
              {busyAudit ? <><span className="spinner" />Loading…</> : 'Apply Filter'}
            </button>
          </div>

          {errorAudit && <div className="alert alert-bad" style={{ marginBottom: 16 }}>{errorAudit}</div>}

          {auditData && (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div className="card-title">Mainframe Audit Events</div>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>{auditData.total} total</span>
              </div>
              {auditData.events.length === 0 ? (
                <div style={{ textAlign: 'center', color: 'var(--muted)', padding: 32 }}>No events recorded yet.</div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      {['Time', 'Type', 'LPAR', 'Resource', 'Action', 'Outcome', 'Detail'].map((h) => (
                        <th key={h} style={{ textAlign: 'left', padding: '6px 8px', color: 'var(--muted)', fontWeight: 500 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {auditData.events.map((ev) => (
                      <tr key={ev.id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '8px', whiteSpace: 'nowrap', color: 'var(--muted)' }}>
                          {new Date(ev.created_at).toLocaleString()}
                        </td>
                        <td style={{ padding: '8px', fontFamily: 'monospace' }}>{ev.event_type}</td>
                        <td style={{ padding: '8px', fontFamily: 'monospace' }}>{ev.lpar_name || '—'}</td>
                        <td style={{ padding: '8px', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {ev.resource || '—'}
                        </td>
                        <td style={{ padding: '8px', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {ev.action || '—'}
                        </td>
                        <td style={{ padding: '8px' }}>
                          <span style={{ color: OUTCOME_COLOR[ev.outcome] ?? 'var(--muted)', fontWeight: 600 }}>
                            {ev.outcome}
                          </span>
                        </td>
                        <td style={{ padding: '8px', color: 'var(--muted)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {ev.detail || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
