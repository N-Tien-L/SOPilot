import React from 'react';
import type { Metadata } from 'next';
import './globals.css';
import { QueryProvider, ThemeProvider, LanguageProvider } from '@/providers';
import { Toaster } from 'react-hot-toast';

export const metadata: Metadata = {
  title: 'Poliwise - AI-powered Enterprise Knowledge Platform',
  description: 'AI-powered Enterprise Knowledge Platform',
  icons: {
    icon: [
      {
        url: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='20' fill='%234f46e5'/><text x='50' y='65' font-size='50' text-anchor='middle' fill='white' font-family='system-ui'>P</text></svg>",
        type: 'image/svg+xml',
      },
    ],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var stored = localStorage.getItem('preferences-storage');
                  if (stored) {
                    var state = JSON.parse(stored).state;
                    if (state && state.theme === 'dark') {
                      document.documentElement.classList.add('dark');
                    }
                  }
                } catch(e) {}
              })();
            `,
          }}
        />
      </head>
      <body>
        <QueryProvider>
          <ThemeProvider>
            <LanguageProvider>
              {children}
            </LanguageProvider>
          </ThemeProvider>
        </QueryProvider>
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: '#363636',
              color: '#fff',
              borderRadius: '8px',
              fontSize: '14px',
            },
            success: {
              iconTheme: {
                primary: '#22c55e',
                secondary: '#fff',
              },
            },
            error: {
              iconTheme: {
                primary: '#ef4444',
                secondary: '#fff',
              },
            },
          }}
        />
      </body>
    </html>
  );
}
