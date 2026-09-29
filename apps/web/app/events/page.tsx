"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, getMe, User } from "../../lib/api";

type Event = { id:string; name:string; slug:string; description:string; status:string; created_at:string };

export default function EventsPage(){
  const [events,setEvents]=useState<Event[]>([]); const [user,setUser]=useState<User|null>(null); const [error,setError]=useState("");
  useEffect(()=>{Promise.all([apiFetch<Event[]>('/events'),getMe().catch(()=>null)]).then(([e,u])=>{setEvents(e);setUser(u as User|null)}).catch(err=>setError(err instanceof Error?err.message:'Failed to load events'))},[]);
  return <main><div className="row" style={{justifyContent:'space-between'}}><div><h2>Events</h2><p className="muted">All events come from PostgreSQL. Empty means empty.</p></div>{(user?.role==='ORGANIZER'||user?.role==='ADMIN')&&<Link className="button" href="/events/new">Create event</Link>}</div>{error&&<div className="error">{error}</div>}<div className="grid">{events.map(e=><div className="card" key={e.id}><div className="row"><span className="pill">{e.status}</span></div><h3>{e.name}</h3><p>{e.description}</p><p className="muted mono">{e.slug}</p><div className="row"><Link className="button secondary" href={`/events/${e.id}`}>Open</Link><Link className="button secondary" href={`/gallery/${e.id}`}>Gallery</Link>{(user?.role==='ORGANIZER'||user?.role==='ADMIN')&&<Link className="button secondary" href={`/organizer/${e.id}`}>Manage</Link>}</div></div>)}{events.length===0&&<div className="card"><p>No events yet.</p></div>}</div></main>;
}
