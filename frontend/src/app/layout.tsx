import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ArXiv Atlas",
  description: "Enter a topic, get a visual map of the research landscape.",
  // Explicitly declares this page as light-themed so browsers/OS dark-mode
  // settings don't auto-invert colors and break text contrast.
  other: {
    "color-scheme": "light",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased" style={{ colorScheme: "light" }}>
      <head>
        <meta name="color-scheme" content="light" />
      </head>
      <body className="min-h-full flex flex-col bg-white font-sans">{children}</body>
    </html>
  );
}
