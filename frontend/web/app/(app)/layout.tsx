import { AppShell } from '@/components/app/AppShell';
import { UploadManager } from '@/components/documents/UploadManager';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell>
      {children}
      <UploadManager />
    </AppShell>
  );
}
