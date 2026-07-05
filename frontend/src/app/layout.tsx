import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Health Copilot",
  description: "Personal health data from Apple Health, Oura Ring & Garmin",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500&family=DM+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
