'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../lib/auth-context';
import {
  apiZosHealth, apiZosLpars, apiZosJobs, apiZosSubmitJob,
  apiZosDatasets, apiZosTranscode, apiZosMQStatus, apiZosMQPut, apiZosMQGet,
  ZOSHealthResponse, LPAROut, JobOut, DatasetOut, MQBridgeStatusResponse, TranscodeResponse,
} from '../../lib/api';

const TAB_LABELS = ['Health', 'Jobs', 'Datasets', 'Transcode', 'MQ Bridge'] as const;
type Tab = typeof TAB_LABELS[number];

function MetricBar({ value, max = 100, color = 'var(--accent)' }: { value: number; max?: number; color?: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div style={{ background: 'var(--border)', borderRadius: 4, height: 6, overflow: 'hidden', flex: 1 }}>
      <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 4, transition: 'width 0.4s ease' }} />
    </div>
  );
}

export default function ZOSPage() {
  const { token, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>('Health');

  // Health
  const [health, setHealth] = useState<ZOSHealthResponse | null>(null);
  const [lpars, setLpars] = useState<LPAROut[]>([]);

  // Jobs
  const [jobs, setJobs] = useState<JobOut[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [jobName, setJobName] = useState('QFJOB01');
  const [jobLpar, setJobLpar] = useState('SYSA');
  const [jobProgram, setJobProgram] = useState('IEFBR14');
  const [jobParm, setJobParm] = useState('');
  const [rawJcl, setRawJcl] = useState('');
  const [useRawJcl, setUseRawJcl] = useState(false);

  // Datasets
  const [datasets, setDatasets] = useState<DatasetOut[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [hlq, setHlq] = useState('QFINTEK');
  const [uploadLines, setUploadLines] = useState('RECORD ONE\nRECORD TWO\nRECORD THREE');
  const [uploadDsn, setUploadDsn] = useState('QFINTEK.JCL.LIB');
  const [uploadResult, setUploadResult] = useState<string>('');
  const [downloadDsn, setDownloadDsn] = useState('QFINTEK.PAYROLL.MASTER');
  const [downloadResult, setDownloadResult] = useState<string[]>([]);

  // Transcode
  const [transcodeText, setTranscodeText] = useState('HELLO FROM QUANTUMFINTEK');
  const [transcodeCp, setTranscodeCp] = useState('cp037');
  const [transcodeMode, setTranscodeMode] = useState('fixed');
  const [transcodeResult, setTranscodeResult] = useState<TranscodeResponse | null>(null);
  const [transcodeHexDump, setTranscodeHexDump] = useState(false);

  // MQ
  const [mqStatus, setMqStatus] = useState<MQBridgeStatusResponse | null>(null);
  const [mqQueue, setMqQueue] = useState('QFINTEK.ORDERS.LOCAL');
  const [mqPayload, setMqPayload] = useState('BUY 100 AAPL @ MKT');
  const [mqPutResult, setMqPutResult] = useState('');
  const [mqGetResult, setMqGetResult] = useState('');

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => { if (!loading && !token) router.replace('/'); }, [token, loading, router]);

  useEffect(() => {
    if (!token) return;
    loadHealth();
    loadLpars();
    loadJobs();
    loadDatasets();
    loadMQStatus();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function run<T>(key: string, fn: () => Promise<T>, set: (v: T) => void) {
    setBusy(key); setError(''); setSuccess('');
    try { set(await fn()); }
    catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); }
    finally { setBusy(null); }
  }

  const loadHealth   = () => run('health',   () => apiZosHealth(token!),                              setHealth);
  const loadLpars    = () => run('lpars',    () => apiZosLpars(token!),                               setLpars);
  const loadJobs     = () => run('jobs',     () => apiZosJobs(token!).then((r) => r.jobs),            setJobs);
  const loadDatasets = () => run('datasets', () => apiZosDatasets.list(token!, hlq).then((r) => r.datasets), setDatasets);
  const loadMQStatus = () => run('mq',       () => apiZosMQStatus(token!),                            setMqStatus);

  async function handleSubmitJob() {
    if (!token) return;
    setBusy('submit'); setError(''); setSuccess('');
    try {
      const job = await apiZosSubmitJob(token, {
        job_name: jobName,
        lpar: jobLpar,
        program: useRawJcl ? undefined : jobProgram,
        parm: jobParm || undefined,
        jcl: useRawJcl ? rawJcl : undefined,
      });
      setSuccess(`Job ${job.job_id} submitted → ${job.status} (RC ${job.return_code ?? job.abend_code ?? '—'})`);
      await loadJobs();
    } catch (e) { setError(e instanceof Error ? e.message : 'Submit failed'); }
    finally { setBusy(null); }
  }

  async function handleUpload() {
    if (!token) return;
    setBusy('upload'); setError('');
    try {
      const r = await apiZosDatasets.upload(token, {
        dsn: uploadDsn, lines: uploadLines.split('\n').filter(Boolean), recfm: 'FB', lrecl: 80, code_page: 'cp037',
      });
      setUploadResult(`✓ ${r.records_written} records written · ${r.byte_count} bytes EBCDIC`);
    } catch (e) { setError(e instanceof Error ? e.message : 'Upload failed'); }
    finally { setBusy(null); }
  }

  async function handleDownload() {
    if (!token) return;
    setBusy('download'); setError('');
    try {
      const r = await apiZosDatasets.download(token, { dsn: downloadDsn, code_page: 'cp037', max_records: 20 });
      setDownloadResult(r.records);
    } catch (e) { setError(e instanceof Error ? e.message : 'Download failed'); }
    finally { setBusy(null); }
  }

  async function handleTranscode() {
    if (!token) return;
    setBusy('transcode'); setError('');
    try {
      const r = await apiZosTranscode(token, { text: transcodeText, code_page: transcodeCp, record_length: 80, mode: transcodeMode, include_hex_dump: transcodeHexDump });
      setTranscodeResult(r);
    } catch (e) { setError(e instanceof Error ? e.message : 'Transcode failed'); }
    finally { setBusy(null); }
  }

  async function handleMQPut() {
    if (!token) return;
    setBusy('mqput'); setError('');
    try {
      const r = await apiZosMQPut(token, { queue_name: mqQueue, payload: mqPayload });
      setMqPutResult(`✓ msg_id=${r.msg_id.slice(0,8)}… depth=${r.queue_depth}`);
      await loadMQStatus();
    } catch (e) { setError(e instanceof Error ? e.message : 'MQ put failed'); }
    finally { setBusy(null); }
  }

  async function handleMQGet() {
    if (!token) return;
    setBusy('mqget'); setError('');
    try {
      const r = await apiZosMQGet(token, mqQueue);
      setMqGetResult(r.msg_id ? `✓ ${r.payload} (${r.msg_type})` : '— Queue empty');
      await loadMQStatus();
    } catch (e) { setError(e instanceof Error ? e.message : 'MQ get failed'); }
    finally { setBusy(null); }
  }

  if (loading || !token) return null;

  return (
    <div className="page">
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div className="page-title">IBM z/OS Integration</div>
            <div className="page-subtitle">
              {health ? `${health.sysplex} sysplex · ${health.online_lpars}/${health.total_lpars} LPARs online` : 'Connecting to mainframe…'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <span className={`badge badge-${health && health.online_lpars === health.total_lpars ? 'ok' : 'warn'}`}>
              {health ? (health.online_lpars === health.total_lpars ? 'All Online' : 'Degraded') : 'Checking…'}
            </span>
            <button className="secondary" onClick={() => { loadHealth(); loadMQStatus(); loadJobs(); }} disabled={busy !== null} style={{ padding: '4px 12px', fontSize: 12 }}>
              {busy ? <span className="spinner" /> : '↺ Refresh'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="alert alert-bad" style={{ marginBottom: 16 }}>{error}</div>}
      {success && <div className="alert alert-ok" style={{ marginBottom: 16 }}>{success}</div>}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
        {TAB_LABELS.map((t) => (
          <button key={t} className={tab === t ? '' : 'secondary'} onClick={() => setTab(t)} style={{ minWidth: 90 }}>
            {t}
          </button>
        ))}
      </div>

      {/* ── Health ── */}
      {tab === 'Health' && (
        <div className="stack">
          <div className="grid-4">
            {[
              { label: 'Sysplex', value: health?.sysplex ?? '—', variant: 'card-accent' },
              { label: 'Online LPARs', value: `${health?.online_lpars ?? '—'} / ${health?.total_lpars ?? '—'}`, variant: 'card-ok' },
              { label: 'MQ Queues', value: health ? Object.keys(health.mq_queues).length : '—', variant: 'card-accent' },
              { label: 'Total Msgs', value: health ? Object.values(health.mq_queues).reduce((a, b) => a + b, 0) : '—', variant: 'card-warn' },
            ].map((m) => (
              <div key={m.label} className={`card ${m.variant}`}>
                <div className="card-title">{m.label}</div>
                <div className="card-value">{m.value}</div>
              </div>
            ))}
          </div>

          {health?.lpars.map((lpar) => (
            <div key={lpar.lpar_name} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 15 }}>{lpar.lpar_name}</div>
                  <div className="text-muted" style={{ fontSize: 12 }}>
                    {lpars.find((l) => l.lpar_name === lpar.lpar_name)?.system_nickname ?? ''} · z/OS {lpars.find((l) => l.lpar_name === lpar.lpar_name)?.zos_version ?? ''} · {lpar.mips.toFixed(0)} MIPS
                  </div>
                </div>
                <span className={`badge badge-${lpar.status === 'ONLINE' ? 'ok' : 'bad'}`}>{lpar.status}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[
                  { label: 'CPU', value: `${lpar.cpu_utilization_pct}%`, pct: lpar.cpu_utilization_pct, color: lpar.cpu_utilization_pct > 80 ? 'var(--bad)' : lpar.cpu_utilization_pct > 60 ? 'var(--warn)' : 'var(--ok)' },
                  { label: 'Memory', value: `${lpar.memory_used_gb} / ${lpar.memory_total_gb} GB (${lpar.memory_used_pct}%)`, pct: lpar.memory_used_pct, color: 'var(--accent)' },
                  { label: 'zIIP', value: `${lpar.ziip_utilization_pct}%`, pct: lpar.ziip_utilization_pct, color: 'var(--accent2)' },
                ].map((row) => (
                  <div key={row.label} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ width: 56, fontSize: 12, color: 'var(--muted)', flexShrink: 0 }}>{row.label}</span>
                    <MetricBar value={row.pct} color={row.color} />
                    <span style={{ width: 160, fontSize: 12, color: 'var(--muted)', textAlign: 'right' }}>{row.value}</span>
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 20, marginTop: 14, fontSize: 12, color: 'var(--muted)' }}>
                <span>Active jobs: <strong>{lpar.active_jobs}</strong></span>
                <span>Initiators: <strong>{lpar.active_initiators}</strong></span>
                <span style={{ marginLeft: 'auto', color: 'var(--subtle)' }}>{new Date(lpar.timestamp).toLocaleTimeString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Jobs ── */}
      {tab === 'Jobs' && (
        <div className="stack">
          <div className="card">
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>Submit JCL Job</div>
            <div className="grid-2" style={{ gap: 10, marginBottom: 12 }}>
              <label>Job Name<input value={jobName} onChange={(e) => setJobName(e.target.value.toUpperCase())} /></label>
              <label>LPAR
                <select value={jobLpar} onChange={(e) => setJobLpar(e.target.value)}>
                  {lpars.map((l) => <option key={l.lpar_name}>{l.lpar_name}</option>)}
                  {lpars.length === 0 && <option>SYSA</option>}
                </select>
              </label>
            </div>
            <label style={{ marginBottom: 10 }}>
              <input type="checkbox" checked={useRawJcl} onChange={(e) => setUseRawJcl(e.target.checked)} style={{ width: 'auto', marginRight: 8 }} />
              Submit raw JCL text
            </label>
            {!useRawJcl ? (
              <div className="grid-2" style={{ gap: 10, marginBottom: 14 }}>
                <label>Program (PGM=)<input value={jobProgram} onChange={(e) => setJobProgram(e.target.value.toUpperCase())} /></label>
                <label>PARM<input value={jobParm} onChange={(e) => setJobParm(e.target.value)} placeholder="optional" /></label>
              </div>
            ) : (
              <label style={{ marginBottom: 14 }}>
                JCL Text
                <textarea value={rawJcl} onChange={(e) => setRawJcl(e.target.value)} rows={8} style={{ fontFamily: 'monospace', fontSize: 12 }} placeholder="//JOBNAME  JOB (ACCT),'PROGRAMMER'..." />
              </label>
            )}
            <button onClick={handleSubmitJob} disabled={busy !== null}>
              {busy === 'submit' ? <><span className="spinner" />Submitting…</> : '▶ Submit Job'}
            </button>
          </div>

          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Job History ({jobs.length})</div>
              <button className="secondary" onClick={loadJobs} disabled={busy !== null} style={{ padding: '4px 12px', fontSize: 12 }}>
                {busy === 'jobs' ? <span className="spinner" /> : 'Refresh'}
              </button>
            </div>
            {jobs.length > 0 ? (
              <div style={{ overflowX: 'auto' }}>
                <table>
                  <thead><tr><th>Job ID</th><th>Name</th><th>LPAR</th><th>Status</th><th>RC</th><th>ABEND</th><th>Submitted</th></tr></thead>
                  <tbody>
                    {jobs.map((j) => (
                      <tr key={j.job_id}>
                        <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{j.job_id}</td>
                        <td style={{ fontWeight: 600 }}>{j.job_name}</td>
                        <td style={{ color: 'var(--muted)', fontSize: 12 }}>{j.lpar}</td>
                        <td><span className={`badge badge-${j.status === 'OUTPUT' ? 'ok' : j.status === 'ACTIVE' ? 'accent' : 'bad'}`}>{j.status}</span></td>
                        <td style={{ fontFamily: 'monospace' }}>{j.return_code != null ? j.return_code : '—'}</td>
                        <td style={{ fontFamily: 'monospace', color: j.abend_code ? 'var(--bad)' : 'var(--subtle)' }}>{j.abend_code ?? '—'}</td>
                        <td style={{ fontSize: 11, color: 'var(--subtle)' }}>{j.submitted_at ? new Date(j.submitted_at).toLocaleString() : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="text-muted" style={{ fontSize: 13 }}>No jobs submitted yet.</div>}
          </div>
        </div>
      )}

      {/* ── Datasets ── */}
      {tab === 'Datasets' && (
        <div className="stack">
          <div className="card">
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 12 }}>Dataset Catalogue</div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
              <input value={hlq} onChange={(e) => setHlq(e.target.value.toUpperCase())} placeholder="HLQ" style={{ width: 160 }} />
              <button className="secondary" onClick={loadDatasets} disabled={busy !== null}>
                {busy === 'datasets' ? <span className="spinner" /> : 'Filter'}
              </button>
            </div>
            {datasets.length > 0 && (
              <table>
                <thead><tr><th>DSN</th><th>RECFM</th><th>LRECL</th><th>BLKSIZE</th><th>Tracks</th></tr></thead>
                <tbody>
                  {datasets.map((d) => (
                    <tr key={d.dsn}>
                      <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{d.dsn}</td>
                      <td><span className="badge badge-accent">{d.recfm}</span></td>
                      <td>{d.lrecl}</td>
                      <td>{d.blksize}</td>
                      <td>{d.size_tracks}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="grid-2">
            <div className="card">
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>Upload → EBCDIC</div>
              <label style={{ marginBottom: 8 }}>Target DSN<input value={uploadDsn} onChange={(e) => setUploadDsn(e.target.value.toUpperCase())} /></label>
              <label style={{ marginBottom: 12 }}>
                Lines (UTF-8)
                <textarea value={uploadLines} onChange={(e) => setUploadLines(e.target.value)} rows={5} style={{ fontFamily: 'monospace', fontSize: 12 }} />
              </label>
              <button onClick={handleUpload} disabled={busy !== null}>
                {busy === 'upload' ? <><span className="spinner" />Uploading…</> : '↑ Upload'}
              </button>
              {uploadResult && <div className="alert alert-ok" style={{ marginTop: 10, fontSize: 12 }}>{uploadResult}</div>}
            </div>

            <div className="card">
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>Download → UTF-8</div>
              <label style={{ marginBottom: 12 }}>
                Source DSN
                <select value={downloadDsn} onChange={(e) => setDownloadDsn(e.target.value)}>
                  {datasets.map((d) => <option key={d.dsn}>{d.dsn}</option>)}
                  {datasets.length === 0 && <option>{downloadDsn}</option>}
                </select>
              </label>
              <button onClick={handleDownload} disabled={busy !== null}>
                {busy === 'download' ? <><span className="spinner" />Downloading…</> : '↓ Download'}
              </button>
              {downloadResult.length > 0 && (
                <div style={{ marginTop: 12, maxHeight: 200, overflowY: 'auto', fontFamily: 'monospace', fontSize: 11, color: 'var(--muted)' }}>
                  {downloadResult.map((r, i) => <div key={i}>{r}</div>)}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Transcode ── */}
      {tab === 'Transcode' && (
        <div className="stack">
          <div className="card">
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 14 }}>EBCDIC ↔ UTF-8 Transcoding</div>
            <div className="grid-2" style={{ gap: 10, marginBottom: 12 }}>
              <label>Code Page
                <select value={transcodeCp} onChange={(e) => setTranscodeCp(e.target.value)}>
                  {['cp037','cp1047','cp1140','cp500','cp273','cp285'].map((cp) => <option key={cp}>{cp}</option>)}
                </select>
              </label>
              <label>Mode
                <select value={transcodeMode} onChange={(e) => setTranscodeMode(e.target.value)}>
                  <option value="fixed">Fixed (pad/truncate to LRECL 80)</option>
                  <option value="raw">Raw (no padding)</option>
                </select>
              </label>
            </div>
            <label style={{ marginBottom: 10 }}>
              <input type="checkbox" checked={transcodeHexDump} onChange={(e) => setTranscodeHexDump(e.target.checked)} style={{ width: 'auto', marginRight: 8 }} />
              Include hex dump
            </label>
            <label style={{ marginBottom: 14 }}>
              UTF-8 Input
              <textarea value={transcodeText} onChange={(e) => setTranscodeText(e.target.value)} rows={4} style={{ fontFamily: 'monospace', fontSize: 13 }} />
            </label>
            <button onClick={handleTranscode} disabled={busy !== null}>
              {busy === 'transcode' ? <><span className="spinner" />Encoding…</> : '⇄ Encode to EBCDIC'}
            </button>
          </div>

          {transcodeResult && (
            <div className="card">
              <div className="grid-3" style={{ marginBottom: 16 }}>
                <div><span className="card-title">Bytes</span><div style={{ fontSize: 18, fontWeight: 700 }}>{transcodeResult.byte_count}</div></div>
                <div><span className="card-title">Code Page</span><div style={{ fontFamily: 'monospace', fontSize: 14 }}>{transcodeCp}</div></div>
                <div><span className="card-title">Mode</span><div style={{ fontSize: 14 }}>{transcodeMode}</div></div>
              </div>
              <div style={{ marginBottom: 12 }}>
                <div className="card-title" style={{ marginBottom: 4 }}>Base64 EBCDIC</div>
                <pre style={{ fontSize: 11, wordBreak: 'break-all', whiteSpace: 'pre-wrap', maxHeight: 100, overflowY: 'auto' }}>{transcodeResult.ebcdic_b64}</pre>
              </div>
              {transcodeResult.hex_dump && (
                <div>
                  <div className="card-title" style={{ marginBottom: 4 }}>Hex Dump (first 256 bytes)</div>
                  <pre style={{ fontSize: 10, lineHeight: 1.5 }}>{transcodeResult.hex_dump}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── MQ Bridge ── */}
      {tab === 'MQ Bridge' && (
        <div className="stack">
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15 }}>Queue Manager: {mqStatus?.queue_manager ?? '—'}</div>
                <div className="text-muted" style={{ fontSize: 12 }}>IBM MQ bridge · in-process stub (swap pymqi for production)</div>
              </div>
              <span className={`badge badge-${mqStatus?.connected ? 'ok' : 'bad'}`}>{mqStatus?.connected ? 'Connected' : 'Disconnected'}</span>
            </div>
            {mqStatus && (
              <table>
                <thead><tr><th>Queue Name</th><th>Depth</th><th>Status</th></tr></thead>
                <tbody>
                  {Object.entries(mqStatus.queues).map(([q, depth]) => (
                    <tr key={q}>
                      <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{q}</td>
                      <td>{depth}</td>
                      <td><span className={`badge badge-${depth > 0 ? 'warn' : 'ok'}`}>{depth > 0 ? `${depth} msg` : 'Empty'}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="grid-2">
            <div className="card">
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>Put Message</div>
              <label style={{ marginBottom: 8 }}>
                Queue
                <select value={mqQueue} onChange={(e) => setMqQueue(e.target.value)}>
                  {mqStatus ? Object.keys(mqStatus.queues).map((q) => <option key={q}>{q}</option>) : <option>{mqQueue}</option>}
                </select>
              </label>
              <label style={{ marginBottom: 12 }}>
                Payload
                <textarea value={mqPayload} onChange={(e) => setMqPayload(e.target.value)} rows={3} style={{ fontFamily: 'monospace', fontSize: 12 }} />
              </label>
              <button onClick={handleMQPut} disabled={busy !== null}>
                {busy === 'mqput' ? <><span className="spinner" />Putting…</> : '↑ Put Message'}
              </button>
              {mqPutResult && <div className="alert alert-ok" style={{ marginTop: 10, fontSize: 12 }}>{mqPutResult}</div>}
            </div>

            <div className="card">
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>Get Message</div>
              <label style={{ marginBottom: 12 }}>
                Queue
                <select value={mqQueue} onChange={(e) => setMqQueue(e.target.value)}>
                  {mqStatus ? Object.keys(mqStatus.queues).map((q) => <option key={q}>{q}</option>) : <option>{mqQueue}</option>}
                </select>
              </label>
              <button onClick={handleMQGet} disabled={busy !== null}>
                {busy === 'mqget' ? <><span className="spinner" />Getting…</> : '↓ Get Message'}
              </button>
              {mqGetResult && (
                <div className={`alert ${mqGetResult.startsWith('✓') ? 'alert-ok' : 'alert-bad'}`} style={{ marginTop: 10, fontSize: 12, fontFamily: 'monospace' }}>
                  {mqGetResult}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
