import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "MetalLLM Marketplace — Apple Metal-powered LLMs for macOS",
  description:
    "A marketplace and MCP server for deploying Metal-accelerated LLMs on Apple Silicon, with a Modal cloud-inference fallback.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <Navbar />
          <main className="min-h-[70vh]">{children}</main>
          <Footer />
        </AuthProvider>
      </body>
    </html>
  );
}
