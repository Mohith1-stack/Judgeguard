"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getMe, apiFetch, User } from "../lib/api";
import { RoleBadge } from "../components/ui";

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    getMe().then(setUser).catch(() => setUser(null));
  }, []);

  async function logout() {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } finally {
      setUser(null);
      window.location.href = "/";
    }
  }

  return (
    <html lang="en">
      <body>
        <div className="ambient ambient-one" />
        <div className="ambient ambient-two" />
        <div className="app-shell">
          <header className="topbar">
            <div className="topbar-inner">
              <Link href="/" className="brand-lockup" aria-label="JudgeGuard home">
                <span className="brand-mark">JG</span>
                <span>
                  <span className="brand-name">JUDGE<span>GUARD</span></span>
                  <small>adaptive judging integrity</small>
                </span>
              </Link>

              <nav className="main-nav">
                <Link href="/events">Events</Link>
                <Link href="/gallery">Gallery</Link>
                {user?.role === "JUDGE" ? <Link href="/judge">Judge workspace</Link> : null}
                {(user?.role === "ORGANIZER" || user?.role === "ADMIN") ? (
                  <Link href="/events">Organizer</Link>
                ) : null}
                {user?.role === "ADMIN" ? <Link href="/admin">Admin</Link> : null}
              </nav>

              <div className="topbar-actions">
                {user ? (
                  <>
                    <div className="identity">
                      <span className="identity-dot" />
                      <span>{user.display_name}</span>
                      <RoleBadge role={user.role} />
                    </div>
                    <button className="button ghost compact" onClick={logout}>Logout</button>
                  </>
                ) : (
                  <>
                    <Link className="button ghost compact" href="/login">Login</Link>
                    <Link className="button compact" href="/register">Create account</Link>
                  </>
                )}
              </div>
            </div>
          </header>

          <main className="page-wrap">{children}</main>

          <footer className="footer">
            <div>
              <strong>JudgeGuard</strong>
              <span className="muted"> self-hosted judging infrastructure</span>
            </div>
            <div className="footer-links">
              <Link href="/events">Events</Link>
              <Link href="/gallery">Gallery</Link>
              <Link href="/login">Access</Link>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
