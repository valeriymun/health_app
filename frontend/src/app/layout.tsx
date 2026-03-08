import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Health Dashboard",
  description: "Personal health data from Apple Health, Oura Ring & Garmin",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
