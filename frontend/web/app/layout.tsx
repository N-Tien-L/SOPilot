import React from 'react';
import type { Metadata } from 'next';
import './globals.css';
import { QueryProvider, SessionProvider } from '@/providers';

export const metadata: Metadata = {
  title: 'SOPilot',
  description: 'Questions and answers over your company SOPs, with verified citations',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <SessionProvider>{children}</SessionProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
