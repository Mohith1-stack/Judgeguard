"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
export default function Embed(){const {eventId}=useParams<{eventId:string}>();const [items,setItems]=useState<any[]>([]);useEffect(()=>{fetch(`http://localhost:8000/api/v1/events/${eventId}/gallery`).then(r=>r.json()).then(d=>setItems(d.items||[])).catch(()=>{})},[eventId]);return <main style={{padding:12}}><h2>JudgeGuard Gallery</h2>{items.map(x=><article key={x.id} className="card"><h3>{x.name}</h3><p>{x.tagline}</p><small>{(x.tech_tags||[]).join(' · ')}</small></article>)}</main>}
