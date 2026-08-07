'use client';

import { usePathname } from 'next/navigation';
import Sidebar from './Sidebar';
import { useAuth } from '../lib/auth-context';

const PUBLIC_PATHS = ['/'];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { token, loading } = useAuth();

  const isPublic = PUBLIC_PATHS.includes(pathname);

  if (loading) {
    return (
      <div style={{ display: 'grid', placeItems: 'center', minHeight: '100vh' }}>
        <div className="spinner" style={{ width: 32, height: 32 }} />
      </div>
    );
  }

  // Auth page — no shell
  if (isPublic || !token) {
    return <>{children}</>;
  }

  // Authenticated shell
  return (
    <div className="shell">
      <Sidebar />
      <div className="main-content">{children}</div>
    </div>
  );
}
