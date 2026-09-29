"use client";
import { FormEvent, useState } from "react";
import { apiFetch } from "../../lib/api";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault(); setError("");
    try { await apiFetch("/auth/register", { method: "POST", body: JSON.stringify({ email, display_name: displayName, password }) }); router.push("/login"); }
    catch (err) { setError(err instanceof Error ? err.message : "Registration failed"); }
  }
  return <main><div className="card" style={{maxWidth:520,margin:"auto"}}><h2>Create account</h2>{error&&<div className="error">{error}</div>}<form onSubmit={submit}><div className="field"><div className="label">Email</div><input type="email" value={email} onChange={e=>setEmail(e.target.value)} required /></div><div className="field"><div className="label">Display name</div><input value={displayName} onChange={e=>setDisplayName(e.target.value)} required /></div><div className="field"><div className="label">Password</div><input type="password" value={password} onChange={e=>setPassword(e.target.value)} minLength={8} required /></div><button>Create participant account</button></form></div></main>;
}
