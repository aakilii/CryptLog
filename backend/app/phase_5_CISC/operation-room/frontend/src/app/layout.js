import './globals.css';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'], variable: '--font-ui', display: 'swap' });

export const metadata = { title: 'SAKSHI LEDGER — National Forensic Log Intelligence Platform', description: 'Government of India' };
export const viewport = { themeColor: '#ffffff' };

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable} ${inter.variable}`}>
      <body className="font-ui">{children}</body>
    </html>
  );
}