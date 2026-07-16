import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Sidebar from "@/components/Sidebar";
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
    >
      <body className="min-h-full flex text-slate-200 bg-slate-900 selection:bg-teal-500/30">
        <Sidebar />
        <main className="flex-1 ml-64 min-h-screen relative overflow-x-hidden">
          {/* Subtle background glow effect */}
          <div className="absolute top-0 left-0 right-0 h-[500px] bg-gradient-to-b from-teal-500/5 to-transparent pointer-events-none" />
          
          <div className="p-8 relative z-10 max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
