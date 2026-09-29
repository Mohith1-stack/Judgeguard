"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, getMe, User } from "../../../../lib/api";

type Question = { id: string; key: string; label: string; description: string; question_type: string; required: boolean; options: string[]; sort_order: number; is_active: boolean };

export default function SubmissionQuestionsPage(){
  const params = useParams<{eventId:string}>();
  const eventId = params.eventId;
  const [me,setMe]=useState<User|null>(null);
  const [questions,setQuestions]=useState<Question[]>([]);
  const [form,setForm]=useState({key:"",label:"",description:"",question_type:"TEXT",required:false,options:"",sort_order:0});
  const [message,setMessage]=useState("");

  const load=()=>apiFetch<Question[]>(`/events/${eventId}/submission-questions`).then(setQuestions).catch(e=>setMessage(e.message));
  useEffect(()=>{getMe().then(setMe).catch(()=>{});load();},[eventId]);

  async function create(e:FormEvent){e.preventDefault();setMessage("");try{await apiFetch<Question>(`/events/${eventId}/submission-questions`,{method:"POST",body:JSON.stringify({...form,options:form.options.split(",").map(x=>x.trim()).filter(Boolean),sort_order:Number(form.sort_order)})});setForm({key:"",label:"",description:"",question_type:"TEXT",required:false,options:"",sort_order:questions.length});await load();setMessage("Question created.");}catch(err){setMessage(err instanceof Error?err.message:"Failed");}}

  async function deactivate(id:string){try{await apiFetch(`/events/${eventId}/submission-questions/${id}`,{method:"DELETE"});await load();}catch(err){setMessage(err instanceof Error?err.message:"Failed");}}

  if(me && !["ORGANIZER","ADMIN"].includes(me.role)) return <main><div className="error">Organizer access required.</div></main>;
  return <main><div className="grid">
    <section className="card"><p className="muted mono">SUBMISSION SCHEMA</p><h2>Custom questions</h2><form onSubmit={create}>
      <label>Key<input required value={form.key} onChange={e=>setForm({...form,key:e.target.value})}/></label>
      <label>Label<input required value={form.label} onChange={e=>setForm({...form,label:e.target.value})}/></label>
      <label>Description<textarea value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label>
      <label>Type<select value={form.question_type} onChange={e=>setForm({...form,question_type:e.target.value})}><option>TEXT</option><option>LONG_TEXT</option><option>URL</option><option>NUMBER</option><option>SINGLE_SELECT</option><option>MULTI_SELECT</option></select></label>
      <label>Options (comma separated)<input value={form.options} onChange={e=>setForm({...form,options:e.target.value})}/></label>
      <label><input type="checkbox" checked={form.required} onChange={e=>setForm({...form,required:e.target.checked})}/> Required</label>
      <button className="button">Add question</button>
    </form>{message&&<div className="notice">{message}</div>}</section>
    <section className="card"><h2>Active questions</h2>{questions.length===0?<p className="muted">No custom questions configured.</p>:questions.map(q=><div className="card" key={q.id}><strong>{q.label}</strong><p className="muted">{q.key} · {q.question_type}{q.required?" · required":""}</p>{q.description&&<p>{q.description}</p>}{q.options.length>0&&<p className="muted">Options: {q.options.join(", ")}</p>}<button className="button secondary" onClick={()=>deactivate(q.id)}>Deactivate</button></div>)}</section>
  </div></main>;
}
