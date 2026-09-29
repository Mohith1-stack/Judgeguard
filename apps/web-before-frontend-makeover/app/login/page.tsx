"use client";
import { FormEvent, useState } from "react";
import { apiFetch } from "../../lib/api";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [email,setEmail]=useState(""); const [password,setPassword]=useState(""); const [error,setError]=useState("");
  async function submit(e:FormEvent){e.preventDefault();setError("");try{const r=await apiFetch<{user:{role:string}}>('/auth/login',{method:'POST',body:JSON.stringify({email,password})}); const role=r.user.role; router.push(role==='JUDGE'?'/judge':role==='ORGANIZER'||role==='ADMIN'?'/events':'/events');}catch(err){setError(err instanceof Error?err.message:'Login failed')}}
  return <main><div className="card" style={{maxWidth:520,margin:"auto"}}><h2>Login</h2>{error&&<div className="error">{error}</div>}<form onSubmit={submit}><div className="field"><div className="label">Email</div><input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></div><div className="field"><div className="label">Password</div><input type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></div><button>Login</button></form></div></main>;
}
