import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import Script from "next/script";
import SmoothScroller from "@/components/SmoothScroller";
import "./globals.css";

/**
 * One superfamily in two voices.
 *
 * Plex Sans carries prose and interface; Plex Mono carries anything that is a
 * record rather than a sentence: section labels, claim references, figures,
 * clause numbers. Keeping both in the same family is what makes the pairing read
 * as a filing system rather than as two fonts.
 */
const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "ClaimSense AI · Claims-integrity workstation",
  description:
    "Reads a hospital bill, adjudicates every line against the governing policy, scores the claim for risk, and traces every conclusion back to the page it came from.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${plexSans.variable} ${plexMono.variable} h-full`}
      suppressHydrationWarning
    >
      <body
        className="min-h-full flex flex-col bg-paper text-ink-900 font-sans antialiased"
        suppressHydrationWarning
      >
        {/*
          Applies the stored theme before first paint. Without this the page
          renders in the system theme and then snaps to the chosen one, a
          visible flash on every navigation, which no amount of CSS can undo
          because the choice lives in localStorage and the server cannot read it.

          next/script rather than a bare <script>: React refuses to execute a
          script tag it meets during a client render and warns about it, whereas
          beforeInteractive is injected into the head of the initial HTML and
          runs ahead of any Next module.
        */}
        <Script id="theme-preference" strategy="beforeInteractive">
          {`(function(){try{var t=localStorage.getItem('claimsense-theme');if(t==='dark'||t==='light'){document.documentElement.dataset.theme=t}}catch(e){}})()`}
        </Script>

        <SmoothScroller>{children}</SmoothScroller>
      </body>
    </html>
  );
}
