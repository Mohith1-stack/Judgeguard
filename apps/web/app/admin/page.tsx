"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

type User={id:string;email:string;display_name:string;role:string;is_active:boolean;email_verified:boolean};
export default function Admin(){const [users,setUsers]=useState<User[]>([]);const [error,setError]=useState('');
useEffect(()=>{apiFetch<User[]>('/admin/users').then(setUsers).catch(e=>setError(e instanceof Error?e.message:'Forbidden'))},[]);
async function role(id:string, value:string){try{await apiFetch(`/admin/users/${id}/role`,{method:'PATCH',body:JSON.stringify({role:value})});setUsers(v=>v.map(u=>u.id===id?{...u,role:value}:u))}catch(e){setError(e instanceof Error?e.message:'Failed')}}
return <main><h2>Administration</h2>{error&&<div className="error">{error}</div>}<div className="card"><table className="table"><thead><tr><th>User</th><th>Role</th><th>Email verified</th><th>Change role</th></tr></thead><tbody>{users.map(u=><tr key={u.id}><td><strong>{u.display_name}</strong><br/><span className="muted">{u.email}</span><div className="mono muted">{u.id}</div></td><td>{u.role}</td><td>{u.email_verified?'yes':'no'}</td><td><select value={u.role} onChange={e=>role(u.id,e.target.value)}><option>PARTICIPANT</option><option>JUDGE</option><option>ORGANIZER</option><option>ADMIN</option></select></td></tr>)}</tbody></table></div></main>}
