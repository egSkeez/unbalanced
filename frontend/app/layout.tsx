import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "./components/Sidebar";
import AuthWrapper from "./components/AuthWrapper";

export const metadata: Metadata = {
  title: "CS2 Pro Balancer",
  description: "Modern CS2 team balancer, draft system, and match tracker",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthWrapper>
          <div className="app-layout">
            <Sidebar />
            <main className="main-content">
              {children}
            </main>
          </div>
        </AuthWrapper>
      </body>
    </html>
  );
}
