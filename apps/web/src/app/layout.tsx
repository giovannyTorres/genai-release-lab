import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "GenAI Release Lab · Evidence before release",
  description:
    "Evaluate synthetic RAG and agent outputs, investigate regressions, and make traceable release decisions.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
