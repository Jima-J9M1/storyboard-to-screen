import type { Metadata } from "next";
import { Bricolage_Grotesque, Instrument_Sans } from "next/font/google";
import "./globals.css";

const display = Bricolage_Grotesque({ subsets: ["latin"], weight: ["400", "600", "800"], variable: "--font-display" });
const text = Instrument_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-text" });

export const metadata: Metadata = {
  title: "Production board",
  description: "Where every film in this repo is, read from the repo itself.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${text.variable}`}>
      <body>{children}</body>
    </html>
  );
}
