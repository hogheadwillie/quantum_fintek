'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../lib/auth-context';
import {
  OrgOut,
  OrgDetailResponse,
  MemberOut,
  apiListOrgs,
  apiCreateOrg,
  apiGetOrg,
  apiInviteMember,
  apiUpdateMemberRole,
  apiRemoveMember,
} from '../../lib/api';

const ROLES = ['member', 'analyst', 'quant', 'trader', 'admin', 'owner'];

export default function OrgsPage() {
  const { token, loading } = useAuth();
  const router = useRouter();

  const [orgs, setOrgs] = useState<OrgOut[]>([]);
  const [selected, setSelected] = useState<OrgDetailResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // create org form
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newSlug, setNewSlug] = useState('');

  // invite form
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');

  useEffect(() => {
    if (!loading && !token) router.replace('/');
  }, [token, loading, router]);

  useEffect(() => {
    if (!token) return;
    loadOrgs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function loadOrgs() {
    if (!token) return;
    setBusy(true);
    setError('');
    try {
      const list = await apiListOrgs(token);
      setOrgs(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load organisations');
    } finally {
      setBusy(false);
    }
  }

  async function selectOrg(org: OrgOut) {
    if (!token) return;
    setBusy(true);
    setError('');
    try {
      const detail = await apiGetOrg(token, org.id);
      setSelected(detail);
      setShowInvite(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load org');
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateOrg(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      await apiCreateOrg(token, newName.trim(), newSlug.trim());
      setNewName('');
      setNewSlug('');
      setShowCreate(false);
      setSuccess('Organisation created.');
      await loadOrgs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create org');
    } finally {
      setBusy(false);
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !selected) return;
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      await apiInviteMember(token, selected.org.id, inviteEmail.trim(), inviteRole);
      setInviteEmail('');
      setInviteRole('member');
      setShowInvite(false);
      setSuccess('Member invited.');
      const detail = await apiGetOrg(token, selected.org.id);
      setSelected(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to invite member');
    } finally {
      setBusy(false);
    }
  }

  async function handleRoleChange(member: MemberOut, newRole: string) {
    if (!token || !selected) return;
    setBusy(true);
    setError('');
    try {
      await apiUpdateMemberRole(token, selected.org.id, member.user_id, newRole);
      const detail = await apiGetOrg(token, selected.org.id);
      setSelected(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update role');
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(member: MemberOut) {
    if (!token || !selected) return;
    if (!confirm(`Remove ${member.username} from ${selected.org.name}?`)) return;
    setBusy(true);
    setError('');
    try {
      await apiRemoveMember(token, selected.org.id, member.user_id);
      const detail = await apiGetOrg(token, selected.org.id);
      setSelected(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove member');
    } finally {
      setBusy(false);
    }
  }

  if (loading || !token) return null;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Organisations</div>
          <div className="page-subtitle">Manage teams, members, and roles</div>
        </div>
        <button className="btn" onClick={() => { setShowCreate((v) => !v); setError(''); setSuccess(''); }}>
          {showCreate ? 'Cancel' : '+ New Org'}
        </button>
      </div>

      {error && <div className="alert alert-bad">{error}</div>}
      {success && <div className="alert alert-ok">{success}</div>}

      {/* Create org form */}
      {showCreate && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-title">Create Organisation</div>
          <form onSubmit={handleCreateOrg} style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <label className="label" style={{ flex: '1 1 200px' }}>
              Name
              <input
                className="input"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Acme Corp"
                required
                minLength={2}
              />
            </label>
            <label className="label" style={{ flex: '1 1 200px' }}>
              Slug
              <input
                className="input"
                value={newSlug}
                onChange={(e) => setNewSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))}
                placeholder="acme-corp"
                required
                pattern="[a-z0-9-]+"
                minLength={2}
              />
            </label>
            <button className="btn" type="submit" disabled={busy}>
              {busy ? 'Creating…' : 'Create'}
            </button>
          </form>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 20, alignItems: 'start' }}>
        {/* Org list */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 13 }}>
            Your Organisations ({orgs.length})
          </div>
          {busy && orgs.length === 0 && (
            <div style={{ padding: 16, color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
          )}
          {orgs.length === 0 && !busy && (
            <div style={{ padding: 16, color: 'var(--muted)', fontSize: 13 }}>No organisations yet.</div>
          )}
          {orgs.map((org) => (
            <button
              key={org.id}
              onClick={() => selectOrg(org)}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                padding: '10px 16px',
                background: selected?.org.id === org.id ? 'var(--surface)' : 'transparent',
                border: 'none',
                borderBottom: '1px solid var(--border)',
                cursor: 'pointer',
                color: 'var(--text)',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 13 }}>{org.name}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                {org.slug} · {org.subscription_level}
              </div>
            </button>
          ))}
        </div>

        {/* Org detail panel */}
        {selected ? (
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div>
                <div className="card-title" style={{ marginBottom: 2 }}>{selected.org.name}</div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                  Slug: <code>{selected.org.slug}</code> · Plan: {selected.org.subscription_level} · ID: {selected.org.id.slice(0, 8)}…
                </div>
              </div>
              <button className="btn ghost" onClick={() => { setShowInvite((v) => !v); setError(''); }}>
                {showInvite ? 'Cancel' : '+ Invite'}
              </button>
            </div>

            {/* Invite form */}
            {showInvite && (
              <form onSubmit={handleInvite} style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 16, padding: 12, background: 'var(--surface)', borderRadius: 6 }}>
                <label className="label" style={{ flex: '1 1 200px' }}>
                  Email
                  <input
                    className="input"
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="colleague@example.com"
                    required
                  />
                </label>
                <label className="label" style={{ flex: '0 0 140px' }}>
                  Role
                  <select className="input" value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}>
                    {ROLES.map((r) => <option key={r}>{r}</option>)}
                  </select>
                </label>
                <button className="btn" type="submit" disabled={busy}>
                  {busy ? 'Inviting…' : 'Invite'}
                </button>
              </form>
            )}

            {/* Member table */}
            <table className="table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th style={{ width: 80 }}></th>
                </tr>
              </thead>
              <tbody>
                {selected.members.map((m) => (
                  <tr key={m.user_id}>
                    <td style={{ fontWeight: 600 }}>{m.username}</td>
                    <td style={{ color: 'var(--muted)', fontSize: 12 }}>{m.email}</td>
                    <td>
                      <select
                        className="input"
                        style={{ padding: '2px 6px', fontSize: 12, height: 28 }}
                        value={m.role}
                        onChange={(e) => handleRoleChange(m, e.target.value)}
                        disabled={busy}
                      >
                        {ROLES.map((r) => <option key={r}>{r}</option>)}
                      </select>
                    </td>
                    <td>
                      <button
                        className="btn ghost"
                        style={{ padding: '2px 8px', fontSize: 11, color: '#c0392b' }}
                        onClick={() => handleRemove(m)}
                        disabled={busy}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="card" style={{ color: 'var(--muted)', fontSize: 13 }}>
            Select an organisation from the left to view details and manage members.
          </div>
        )}
      </div>
    </div>
  );
}
