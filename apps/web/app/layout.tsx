import "./globals.css";
import Link from "next/link";

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="nav">
            <Link href="/" className="brand">JUDGE<span className="muted">GUARD</span></Link>
            <nav className="navlinks">
              <Link href="/events">Events</Link>
              <Link href="/gallery">Gallery</Link>
              <Link href="/login" className="button secondary">Login</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
