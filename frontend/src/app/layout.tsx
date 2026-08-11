import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import SmoothScroller from "@/components/SmoothScroller";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ClaimSense AI | Medical Claim Auditing",
  description: "AI-powered medical claim auditing and appeal generation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body 
        className="min-h-full flex flex-col text-white bg-[#000000] selection:bg-teal-500/30"
        suppressHydrationWarning
      >
        <SmoothScroller>
          {children}
        </SmoothScroller>
      </body>
    </html>
  );
}
