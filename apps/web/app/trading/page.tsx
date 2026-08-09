'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { useAuth } from '../../lib/auth-context';
import {
  apiPlaceOrder, apiListOrders, apiPositions, apiMarketData,
  OrderOut, PositionsResponse, MarketDataResponse,
  API_URL,
} from '../../lib/api';

const DEFAULT_SYMBOLS = 'AAPL,MSFT,GOOGL,AMZN,NVDA,TSLA,JPM,BTC-USD';

export default function TradingPage() {
  const { token, loading } = useAuth();
  const router = useRouter();

  const [quotes, setQuotes] = useState<MarketDataResponse['quotes']>([]);
  const [orders, setOrders] = useState<OrderOut[]>([]);
  const [positions, setPositions] = useState<PositionsResponse | null>(null);
  const [priceHistory, setPriceHistory] = useState<{ t: string; price: number }[]>([]);
  const [focusSymbol, setFocusSymbol] = useState('AAPL');

  const [orderSymbol, setOrderSymbol] = useState('AAPL');
  const [orderSide, setOrderSide] = useState<'buy' | 'sell'>('buy');
  const [orderQty, setOrderQty] = useState('10');
  const [orderType, setOrderType] = useState<'market' | 'limit' | 'stop'>('market');
  const [limitPrice, setLimitPrice] = useState('');

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!loading && !token) router.replace('/');
  }, [token, loading, router]);

  // Connect WebSocket for live quotes
  useEffect(() => {
    if (!token) return;
    const wsUrl = API_URL.replace(/^http/, 'ws') + `/ws/market-data?symbols=${DEFAULT_SYMBOLS}&interval_ms=1500`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onmessage = (evt) => {
      try {
        const data: MarketDataResponse['quotes'] = JSON.parse(evt.data);
        setQuotes(data);
        // Build price history for focused symbol
        const q = data.find((q) => q.symbol === focusSymbol);
        if (q) {
          const now = new Date().toLocaleTimeString();
          setPriceHistory((prev) => [...prev.slice(-59), { t: now, price: q.last }]);
        }
      } catch {/* ignore */}
    };
    ws.onerror = () => {
      // Fallback to REST if WebSocket fails
      if (token) loadMarketData(token);
    };
    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Update price history when focus symbol changes
  useEffect(() => {
    setPriceHistory([]);
  }, [focusSymbol]);

  async function loadMarketData(tok: string) {
    try {
      const d = await apiMarketData(tok, DEFAULT_SYMBOLS);
      setQuotes(d.quotes);
    } catch {/* ignore */}
  }

  async function loadOrders() {
    if (!token) return;
    setBusy('orders');
    try {
      const d = await apiListOrders(token);
      setOrders(d.orders);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed');
    } finally {
      setBusy(null);
    }
  }

  async function loadPositions() {
    if (!token) return;
    setBusy('positions');
    try {
      const d = await apiPositions(token);
      setPositions(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed');
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    if (!token) return;
    loadOrders();
    loadPositions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handlePlaceOrder() {
    if (!token) return;
    setError('');
    setSuccess('');
    setBusy('place');
    try {
      const order = await apiPlaceOrder(token, {
        symbol: orderSymbol.toUpperCase(),
        side: orderSide,
        order_type: orderType,
        quantity: parseFloat(orderQty),
        limit_price: orderType === 'limit' ? parseFloat(limitPrice) : undefined,
      });
      setSuccess(`Order ${order.id.slice(0, 8)}… placed — ${order.status}`);
      await loadOrders();
      await loadPositions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Order failed');
    } finally {
      setBusy(null);
    }
  }

  if (loading || !token) return null;

  const focusQuote = quotes.find((q) => q.symbol === focusSymbol);

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Trading</div>
        <div className="page-subtitle">Live market data · Order management · Positions</div>
      </div>

      {error && <div className="alert alert-bad" style={{ marginBottom: 16 }}>{error}</div>}
      {success && <div className="alert alert-ok" style={{ marginBottom: 16 }}>{success}</div>}

      {/* ── Market ticker strip ── */}
      <div style={{ overflowX: 'auto', marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 10, minWidth: 'max-content', paddingBottom: 4 }}>
          {quotes.map((q) => (
            <button
              key={q.symbol}
              className={focusSymbol === q.symbol ? '' : 'ghost'}
              onClick={() => setFocusSymbol(q.symbol)}
              style={{ padding: '6px 14px', minWidth: 110, textAlign: 'left' }}
            >
              <div style={{ fontWeight: 700, fontSize: 13 }}>{q.symbol}</div>
              <div style={{ fontSize: 12 }}>{q.last.toFixed(2)}</div>
              <div style={{ fontSize: 11, color: q.change_pct >= 0 ? 'var(--ok)' : 'var(--bad)' }}>
                {q.change_pct >= 0 ? '+' : ''}{q.change_pct.toFixed(2)}%
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 24 }}>
        {/* ── Price chart ── */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>{focusSymbol}</div>
              {focusQuote && (
                <div style={{ fontSize: 13, color: 'var(--muted)' }}>
                  Bid <span style={{ color: 'var(--bad)' }}>{focusQuote.bid.toFixed(4)}</span>
                  {' '}·{' '}
                  Ask <span style={{ color: 'var(--ok)' }}>{focusQuote.ask.toFixed(4)}</span>
                  {' '}·{' '}
                  Vol {focusQuote.volume.toLocaleString()}
                </div>
              )}
            </div>
            {focusQuote && (
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{focusQuote.last.toFixed(2)}</div>
                <div style={{ fontSize: 12, color: focusQuote.change_pct >= 0 ? 'var(--ok)' : 'var(--bad)' }}>
                  {focusQuote.change_pct >= 0 ? '▲' : '▼'} {Math.abs(focusQuote.change_pct).toFixed(3)}%
                </div>
              </div>
            )}
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={priceHistory} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#34d48a" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#34d48a" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1e2d4a" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="t" tick={{ fontSize: 9 }} stroke="#4e6485" tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis
                tick={{ fontSize: 10 }}
                stroke="#4e6485"
                tickLine={false}
                axisLine={false}
                domain={['auto', 'auto']}
                tickFormatter={(v) => v.toFixed(1)}
              />
              <Tooltip
                contentStyle={{ background: '#0e1628', border: '1px solid #1e2d4a', borderRadius: 8, fontSize: 12 }}
                formatter={(v) => [typeof v === 'number' ? v.toFixed(4) : v, 'Last']}
              />
              <Area type="monotone" dataKey="price" stroke="#34d48a" strokeWidth={2} fill="url(#priceGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* ── Order ticket ── */}
        <div className="card">
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>Place Order</div>
          <div className="stack" style={{ gap: 12 }}>
            <div className="grid-2" style={{ gap: 10 }}>
              <label>
                Symbol
                <input
                  value={orderSymbol}
                  onChange={(e) => setOrderSymbol(e.target.value.toUpperCase())}
                  placeholder="AAPL"
                  style={{ textTransform: 'uppercase' }}
                />
              </label>
              <label>
                Quantity
                <input
                  type="number"
                  value={orderQty}
                  onChange={(e) => setOrderQty(e.target.value)}
                  min="0.01"
                  step="1"
                />
              </label>
            </div>

            <div className="grid-2" style={{ gap: 10 }}>
              <label>
                Side
                <select value={orderSide} onChange={(e) => setOrderSide(e.target.value as 'buy' | 'sell')}>
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </select>
              </label>
              <label>
                Type
                <select value={orderType} onChange={(e) => setOrderType(e.target.value as typeof orderType)}>
                  <option value="market">Market</option>
                  <option value="limit">Limit</option>
                  <option value="stop">Stop</option>
                </select>
              </label>
            </div>

            {(orderType === 'limit' || orderType === 'stop') && (
              <label>
                {orderType === 'limit' ? 'Limit Price' : 'Stop Price'}
                <input
                  type="number"
                  value={limitPrice}
                  onChange={(e) => setLimitPrice(e.target.value)}
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                />
              </label>
            )}

            <button
              onClick={handlePlaceOrder}
              disabled={busy !== null}
              style={{ background: orderSide === 'buy' ? 'var(--ok)' : 'var(--bad)', borderColor: 'transparent' }}
            >
              {busy === 'place' ? <><span className="spinner" />Placing…</> : `${orderSide === 'buy' ? 'Buy' : 'Sell'} ${orderSymbol || '—'}`}
            </button>
          </div>
        </div>
      </div>

      {/* ── Positions ── */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>
            Positions ({positions?.total_symbols ?? 0})
          </div>
          <button className="secondary" onClick={loadPositions} disabled={busy !== null} style={{ padding: '4px 12px', fontSize: 12 }}>
            {busy === 'positions' ? <span className="spinner" /> : 'Refresh'}
          </button>
        </div>
        {positions && positions.positions.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Quantity</th>
                  <th>Avg Fill</th>
                  <th>Est. Value</th>
                </tr>
              </thead>
              <tbody>
                {positions.positions.map((p) => (
                  <tr key={p.symbol}>
                    <td style={{ fontWeight: 700 }}>{p.symbol}</td>
                    <td>
                      <span className={`badge badge-${p.side === 'long' ? 'ok' : 'bad'}`}>{p.side}</span>
                    </td>
                    <td>{p.quantity.toFixed(4)}</td>
                    <td style={{ fontFamily: 'monospace' }}>{p.avg_fill_price.toFixed(4)}</td>
                    <td style={{ fontFamily: 'monospace', color: 'var(--accent)' }}>
                      ${p.current_value_estimate.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ color: 'var(--subtle)', fontSize: 13 }}>No open positions.</div>
        )}
      </div>

      {/* ── Orders ── */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>Order History ({orders.length})</div>
          <button className="secondary" onClick={loadOrders} disabled={busy !== null} style={{ padding: '4px 12px', fontSize: 12 }}>
            {busy === 'orders' ? <span className="spinner" /> : 'Refresh'}
          </button>
        </div>
        {orders.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Type</th>
                  <th>Qty</th>
                  <th>Fill</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id}>
                    <td style={{ fontSize: 11, color: 'var(--subtle)', whiteSpace: 'nowrap' }}>
                      {new Date(o.created_at).toLocaleString()}
                    </td>
                    <td style={{ fontWeight: 600 }}>{o.symbol}</td>
                    <td>
                      <span className={`badge badge-${o.side === 'buy' ? 'ok' : 'bad'}`}>{o.side}</span>
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--muted)' }}>{o.order_type}</td>
                    <td style={{ fontFamily: 'monospace' }}>{o.quantity}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>
                      {o.fill_price != null ? o.fill_price.toFixed(4) : '—'}
                    </td>
                    <td>
                      <span className={`badge badge-${o.status === 'filled' ? 'ok' : o.status === 'cancelled' ? 'neutral' : o.status === 'rejected' ? 'bad' : 'accent'}`}>
                        {o.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ color: 'var(--subtle)', fontSize: 13 }}>No orders yet.</div>
        )}
      </div>
    </div>
  );
}
