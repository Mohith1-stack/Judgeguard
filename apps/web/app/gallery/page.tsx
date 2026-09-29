"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
type Event={id:string;name:string;status:string};
export default function Galleries(){const [events,setEvents]=useState<Event[]>([]);useEffect(()=>{apiFetch<Event[]>('/events').then(setEvents).catch(()=>{})},[]);return <main><h2>Galleries</h2><div className="grid">{events.map(e=><div className="card" key={e.id}><span className="pill">{e.status}</span><h3>{e.name}</h3><Link className="button secondary" href={`/gallery/${e.id}`}>Open gallery</Link></div>)}{events.length===0&&<div className="card"><p>No events found.</p></div>}</div></main>}
