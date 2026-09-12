import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ModalityOps — Signal observability",
  description:
    "Inspect timing, diagnose signal quality, and align EEG, audio and video with reproducible evidence.",
  icons: {
    icon: `${process.env.NEXT_PUBLIC_BASE_PATH || ""}/favicon.svg`,
    shortcut: `${process.env.NEXT_PUBLIC_BASE_PATH || ""}/favicon.svg`,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}
