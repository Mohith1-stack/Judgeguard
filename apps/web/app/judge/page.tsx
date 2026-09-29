"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, getMe, User } from "../../lib/api";
type Event={id:string;name:string;status:string};
export default function JudgeHome(){const [events,setEvents]=useState<Event[]>([]);const [me,setMe]=useState<User|null>(null);useEffect(()=>{getMe().then(setMe).catch(()=>{});apiFetch<Event[]>('/events').then(setEvents).catch(()=>{})},[]);return <main><h2>Judge Workspace</h2><p className="muted">Signed in as {me?.display_name??'guest'}.</p>{me?.role!=='JUDGE'&&<div className="error">Your account is not a judge. An administrator must assign the JUDGE role.</div>}<div className="grid">{events.map(e=><div className="card" key={e.id}><h3>{e.name}</h3><p>{e.status}</p><Link className="button" href={`/judge/${e.id}`}>Open queue</Link></div>)}</div></main>}
