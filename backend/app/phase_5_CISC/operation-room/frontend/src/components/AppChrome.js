'use client';

import { useMemo } from 'react';
import { usePathname } from 'next/navigation';
import Sidebar from '@operation-room/components/Sidebar';
import TopHeader from '@operation-room/components/TopHeader';

const isStudioPath = (pathname) => {
  if (!pathname) return false;
  return pathname.includes('/studio-v4');
};

export default function AppChrome({ children }) {
  const pathname = usePathname();
  const studioRoute = useMemo(() => isStudioPath(pathname), [pathname]);

  if (studioRoute) {
    return <main className="studio-main-content">{children}</main>;
  }

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <TopHeader />
        {children}
      </main>
    </div>
  );
}
