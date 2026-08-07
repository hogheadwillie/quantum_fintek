'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from 'recharts';
import { useAuth } from '../../lib/auth-context';
import {
  apiAnomaly, apiSentiment,
  sampleMatrix,
  AnomalyResult, SentimentResult,
} from '../../lib/api';

const SAMPLE_HEADLINES = [
  'Company reports record profit and strong revenue growth, upgraded by analysts',
  'Market faces headwinds as recession risk and debt concerns grow',
  'Earnings beat expectations with robust momentum and optimistic outlook',
  'Regulatory penalty and fraud investigation weigh on quarterly results',
  'Dividend increase signals confident and resilient balance sheet',
  'Volatile trading session amid uncertain rate policy and weak demand',
  'Strong expansion into emerging markets drives long-term growth opportunity',
  'Cost-cutting measures and layoffs signal pressure on operating margins',
];

export default function AIPage() {
  const { token, loading } = useAuth();
  const router = useRouter();

  const [anomalyResult, setAnomalyResult] = useState<AnomalyResult | null>(null);
  const [sentimentResult, setSentimentResult] = useState<SentimentResult | null>(null);
  const [headlines, setHeadlines] = useState(SAMPLE_HEADLINES.join('\n'));

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

  const handleAnomaly = () =>
    run('anomaly', () => apiAnomaly(token, sampleMatrix(60, 5), 0.08), setAnomalyResult);

  const handleSentiment = () => {
    const texts = headlines.split('\n').map((s) => s.trim()).filter(Boolean);
    run('sentiment', () => apiSentiment(token, texts), setSentimentResult);
  };

  // Scatter data: colour by anomaly label
  const scatterData = anomalyResult
    ? anomalyResult.scores.map((s, i) => ({
        index: i,
        score: parseFloat(s.toFixed(4)),
        label: anomalyResult.labels[i],
      }))
    : [];

  const inliers  = scatterData.filter((d) => d.label === 1);
  const outliers = scatterData.filter((d) => d.label === -1);

  const sentBarData = sentimentResult
    ? [
        { label: 'Positive', count: sentimentResult.n_positive },
        { label: 'Neutral',  count: sentimentResult.n_neutral },
        { label: 'Negative', count: sentimentResult.n_negative },
      ]
    : [];

  const SENTIMENT_COLORS: Record<string, string> = {
    positive: 'var(--ok)',
    neutral: 'var(--muted)',
    negative: 'var(--bad)',
  };

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">AI Intelligence</div>
        <div className="page-subtitle">
          Anomaly detection · Financial sentiment analysis
        </div>
      </div>

      {error && <div className="alert alert-bad" style={{ marginBottom: 20 }}>{error}</div>}

      <div className="stack">

        {/* ── Anomaly Detection ── */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Anomaly Detection</div>
              <div className="text-muted" style={{ fontSize: 13 }}>
                Isolation Forest · 60 samples · 5 features · contamination 8%
              </div>
            </div>
            <button onClick={handleAnomaly} disabled={busy !== null}>
              {busy === 'anomaly' ? <><span className="spinner" />Running…</> : 'Run Detection'}
            </button>
          </div>

          {anomalyResult && (
            <>
              {/* Summary row */}
              <div className="grid-3" style={{ marginBottom: 20 }}>
                {[
                  { label: 'Total Samples', value: anomalyResult.labels.length, variant: 'card-accent' },
                  { label: 'Inliers', value: anomalyResult.labels.filter((x) => x === 1).length, variant: 'card-ok' },
                  { label: 'Anomalies', value: anomalyResult.n_anomalies, variant: 'card-bad' },
                ].map((m) => (
                  <div key={m.label} className={`card ${m.variant}`} style={{ background: 'var(--surface2)' }}>
                    <div className="card-title">{m.label}</div>
                    <div className="card-value" style={{ fontSize: 22 }}>{m.value}</div>
                  </div>
                ))}
              </div>

              {/* Score distribution */}
              <div className="card-title" style={{ marginBottom: 8 }}>Decision Scores (lower = more anomalous)</div>
              <ResponsiveContainer width="100%" height={200}>
                <ScatterChart margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#1e2d4a" strokeDasharray="3 3" />
                  <XAxis dataKey="index" name="Sample" stroke="#4e6485" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis dataKey="score" name="Score" stroke="#4e6485" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#0e1628', border: '1px solid #1e2d4a', borderRadius: 8, fontSize: 12 }}
                    formatter={(v, name) => [typeof v === 'number' ? v.toFixed(4) : v, name]}
                  />
                  <Scatter name="Inlier"  data={inliers}  fill="#34d48a" opacity={0.8} />
                  <Scatter name="Anomaly" data={outliers} fill="#f05252" opacity={0.9} />
                </ScatterChart>
              </ResponsiveContainer>

              {/* Legend */}
              <div className="row" style={{ marginTop: 8, gap: 16 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--muted)' }}>
                  <span style={{ width: 10, height: 10, background: '#34d48a', borderRadius: 2, display: 'inline-block' }} /> Inlier
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--muted)' }}>
                  <span style={{ width: 10, height: 10, background: '#f05252', borderRadius: 2, display: 'inline-block' }} /> Anomaly
                </span>
              </div>
            </>
          )}
        </div>

        {/* ── Sentiment Analysis ── */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Sentiment Analysis</div>
              <div className="text-muted" style={{ fontSize: 13 }}>
                Lexicon-based financial NLP · Edit headlines below
              </div>
            </div>
            <button onClick={handleSentiment} disabled={busy !== null}>
              {busy === 'sentiment' ? <><span className="spinner" />Analysing…</> : 'Analyse Sentiment'}
            </button>
          </div>

          <label style={{ marginBottom: 16 }}>
            Headlines (one per line)
            <textarea
              value={headlines}
              onChange={(e) => setHeadlines(e.target.value)}
              rows={6}
              style={{ fontFamily: 'ui-monospace, monospace', fontSize: 12.5, resize: 'vertical' }}
            />
          </label>

          {sentimentResult && (
            <>
              {/* Summary */}
              <div className="grid-4" style={{ marginBottom: 20 }}>
                {[
                  { label: 'Avg. Score', value: sentimentResult.average_score.toFixed(3), variant: sentimentResult.average_score >= 0 ? 'card-ok' : 'card-bad' },
                  { label: 'Positive', value: sentimentResult.n_positive, variant: 'card-ok' },
                  { label: 'Neutral', value: sentimentResult.n_neutral, variant: 'card-accent' },
                  { label: 'Negative', value: sentimentResult.n_negative, variant: 'card-bad' },
                ].map((m) => (
                  <div key={m.label} className={`card ${m.variant}`} style={{ background: 'var(--surface2)' }}>
                    <div className="card-title">{m.label}</div>
                    <div className="card-value" style={{ fontSize: 22 }}>{m.value}</div>
                  </div>
                ))}
              </div>

              {/* Distribution bar chart */}
              <div className="grid-2">
                <div>
                  <div className="card-title" style={{ marginBottom: 8 }}>Label Distribution</div>
                  <ResponsiveContainer width="100%" height={140}>
                    <BarChart data={sentBarData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                      <CartesianGrid stroke="#1e2d4a" vertical={false} />
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="#4e6485" tickLine={false} axisLine={false} />
                      <YAxis tick={{ fontSize: 11 }} stroke="#4e6485" tickLine={false} axisLine={false} />
                      <Tooltip contentStyle={{ background: '#0e1628', border: '1px solid #1e2d4a', borderRadius: 8, fontSize: 12 }} />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                        {sentBarData.map((entry, i) => (
                          <Cell key={i} fill={entry.label === 'Positive' ? '#34d48a' : entry.label === 'Negative' ? '#f05252' : '#7d96c0'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div>
                  <div className="card-title" style={{ marginBottom: 8 }}>Per-Document Results</div>
                  <div style={{ maxHeight: 160, overflowY: 'auto' }}>
                    <table>
                      <thead><tr><th>#</th><th>Label</th><th>Score</th><th>Confidence</th></tr></thead>
                      <tbody>
                        {sentimentResult.results.map((r, i) => (
                          <tr key={i}>
                            <td className="text-muted">{i + 1}</td>
                            <td>
                              <span className={`badge badge-${r.label === 'positive' ? 'ok' : r.label === 'negative' ? 'bad' : 'neutral'}`}>
                                {r.label}
                              </span>
                            </td>
                            <td style={{ color: SENTIMENT_COLORS[r.label] }}>{r.score.toFixed(3)}</td>
                            <td className="text-muted">{(r.confidence * 100).toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
