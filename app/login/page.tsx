"use client";
import { FormEvent, useState } from "react";
import { ArrowRight, ShieldCheck, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import styles from "./login.module.css";

const API=process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000/api/v1";

export default function Login(){
 const router=useRouter(); const [email,setEmail]=useState(""); const [password,setPassword]=useState(""); const [busy,setBusy]=useState(false); const [error,setError]=useState("");
 async function submit(e:FormEvent){e.preventDefault();setBusy(true);setError("");
  try{const r=await fetch(API+"/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Login failed");localStorage.setItem("rivu_access_token",d.tokens.access_token);localStorage.setItem("rivu_user",JSON.stringify(d.user));localStorage.setItem("rivu_org",JSON.stringify(d.organization));router.push("/dashboard");}catch(err){setError(err instanceof Error?err.message:"Unable to sign in");}finally{setBusy(false)}}
 return <main className={styles.page}><div className={styles.glow}/><header><a href="/" className={styles.logo}><span>R</span> Rivu<span>ai</span></a><span className={styles.secure}><ShieldCheck size={15}/> Secure workspace</span></header>
 <section className={styles.card}><div className={styles.kicker}><Sparkles size={14}/> AI-NATIVE DATA REFINERY</div><h1>Welcome back.</h1><p>Sign in to your data workspace and continue refining.</p>
 <form onSubmit={submit}><label>Email<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required placeholder="you@company.com"/></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required placeholder="••••••••"/></label>{error&&<div className={styles.error}>{error}</div>}<button disabled={busy}>{busy?"Signing in…":"Enter Rivu"} <ArrowRight size={17}/></button></form>
 <div className={styles.note}><ShieldCheck size={16}/> Your data stays inside your authenticated workspace.</div></section>
 <footer>RIVU BY WATERTING · DATA REFINERY</footer></main>
}
