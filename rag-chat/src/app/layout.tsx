import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ABC Beverage - RAG Chat",
  description: "AI Chat สำหรับถามข้อมูลนโยบายบริษัท ABC Beverage",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="th">
      <body className="min-h-screen bg-gray-50">{children}</body>
    </html>
  );
}
