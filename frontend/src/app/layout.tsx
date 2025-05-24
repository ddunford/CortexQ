import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Enterprise RAG System',
  description: 'AI-powered document search and chat system',
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