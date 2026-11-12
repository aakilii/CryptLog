import type { Metadata } from "next"
import { GeistSans } from "geist/font/sans"
import { GeistMono } from "geist/font/mono"
import { Inter } from "next/font/google"

import "@operation-room/app/globals.css"

const inter = Inter({ subsets: ["latin"], variable: "--font-ui", display: "swap" })

export const metadata: Metadata = {
  title: "Operation Room | SAKSHI LEDGER",
  description: "Case workspace — embedded from app/phase_5_CISC/operation-room/frontend",
}

/**
 * Segment layout only (no <html>): the Operation Room root layout in the standalone app
 * wraps <html>; here we apply the same font variables and global styles under the main shell.
 */
export default function OperationRoomSegmentLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div
      className={`${GeistSans.variable} ${GeistMono.variable} ${inter.variable} font-ui min-h-full bg-background text-foreground`}
    >
      {children}
    </div>
  )
}
