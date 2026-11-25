import type { Metadata } from "next";
import { Bricolage_Grotesque, Instrument_Sans, Noto_Sans_Ethiopic } from "next/font/google";
import "./globals.css";

const display = Bricolage_Grotesque({ subsets: ["latin"], weight: ["400", "600", "800"], variable: "--font-display" });
const text = Instrument_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-text" });
// Amharic narration is shown on the board. The Latin faces have no Ge'ez letters, so one is named for them.
const ethiopic = Noto_Sans_Ethiopic({ subsets: ["ethiopic"], weight: ["400", "600"], variable: "--font-ethiopic" });

export const metadata: Metadata = {
  title: "Production board",
  description: "Where every film in this repo is, read from the repo itself.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${text.variable} ${ethiopic.variable}`}>
      <body>{children}</body>
    </html>
  );
}
