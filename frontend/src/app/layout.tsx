import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AXIS — Workforce scheduling",
  description: "AXIS frontend — orchestrator, scheduling, and roster views",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
