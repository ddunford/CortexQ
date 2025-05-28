import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'CortexQ - Ask Smarter. Know Faster.',
  description: 'AI-powered knowledge management and intelligent conversation platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
} 