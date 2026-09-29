"use client";
import { FormEvent, useState } from "react";
import { apiFetch } from "../../../lib/api";
import { useRouter } from "next/navigation";

export default function NewEvent(){
  const router=useRouter();
  const [form,setForm]=useState({name:'',slug:'',description:'',registration_opens_at:'',registration_closes_at:'',submission_opens_at:'',submission_deadline:'',judging_opens_at:'',judging_deadline:'',voting_opens_at:'',voting_deadline:''});
  const [error,setError]=useState('');
  const set=(k:string,v:string)=>setForm(x=>({...x,[k]:v}));
  async function submit(e:FormEvent){e.preventDefault();setError('');try{const body=Object.fromEntries(Object.entries(form).filter(([,v])=>v!==''));const r=await apiFetch<{id:string}>('/events',{method:'POST',body:JSON.stringify(body)});router.push(`/events/${r.id}`)}catch(err){setError(err instanceof Error?err.message:'Failed')}}
  return <main><div className="card" style={{maxWidth:760,margin:'auto'}}><h2>Create event</h2>{error&&<div className="error">{error}</div>}<form onSubmit={submit}><div className="field"><div className="label">Event name</div><input value={form.name} onChange={e=>set('name',e.target.value)} required/></div><div className="field"><div className="label">Slug</div><input value={form.slug} onChange={e=>set('slug',e.target.value)} pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$" required/></div><div className="field"><div className="label">Description</div><textarea rows={5} value={form.description} onChange={e=>set('description',e.target.value)}/></div><div className="grid">{(['registration_opens_at','registration_closes_at','submission_opens_at','submission_deadline','judging_opens_at','judging_deadline','voting_opens_at','voting_deadline'] as const).map(k=><div className="field" key={k}><div className="label">{k.replaceAll('_',' ')}</div><input type="datetime-local" value={form[k]} onChange={e=>set(k,e.target.value)}/></div>)}</div><button>Create event</button></form></div></main>
}
