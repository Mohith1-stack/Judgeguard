import Link from "next/link";

export default function Home() {
  return (
    <main>
      <section className="card">
        <p className="muted mono">ADAPTIVE · ATTACK-RESISTANT · SELF-HOSTED</p>
        <h1>JUDGE<span className="muted">GUARD</span></h1>
        <p>Event judging infrastructure with a transparent judging-integrity engine.</p>
        <div className="grid">
          <div className="card"><h3>T1 Core</h3><p>Authentication, events, teams, submissions and public gallery.</p></div>
          <div className="card"><h3>T2 Judging</h3><p>Weighted rubrics, isolated evaluations, assignment and normalization.</p></div>
          <div className="card"><h3>JudgeGuard</h3><p>Influence, minimum flip sets, stability, sensitivity and adaptive review.</p></div>
        </div>
        <div className="row"><Link className="button" href="/register">Create account</Link><Link className="button secondary" href="/events">Browse events</Link></div>
      </section>
    </main>
  );
}
