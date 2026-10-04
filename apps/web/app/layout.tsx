import type { Metadata } from "next";
import Link from "next/link";
import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Plot Ledger",
  description: "Crop suitability, risk, and profit scenarios for Philippine farms.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,520;9..144,650&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Providers>
          <div className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
            <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-gold">Crop intelligence</p>
                <Link href="/" className="display text-4xl text-canopy">
                  Plot Ledger
                </Link>
              </div>
              <nav className="flex gap-2 text-sm">
                <Link className="rounded-full border border-canopy/20 bg-paper px-4 py-2 text-canopy" href="/">
                  Analysis
                </Link>
                <Link className="rounded-full border border-canopy/20 bg-paper px-4 py-2 text-canopy" href="/market">
                  Market
                </Link>
                <Link className="rounded-full border border-canopy/20 bg-paper px-4 py-2 text-canopy" href="/knowledge">
                  Knowledge
                </Link>
              </nav>
            </header>
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
