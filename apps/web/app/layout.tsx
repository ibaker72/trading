import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trading Bot Dashboard",
  description: "Intraday trading bot control panel",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-white min-h-screen font-mono antialiased">
        {children}
      </body>
    </html>
  );
}
