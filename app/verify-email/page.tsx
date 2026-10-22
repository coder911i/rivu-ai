"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import styles from "../login/login.module.css";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

export default function VerifyEmailPage() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("Checking verification link…");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const value = new URLSearchParams(window.location.search).get("token") || "";
    const frame = window.requestAnimationFrame(() => {
      setToken(value);
      if (!value) setMessage("Verify your email to activate your Rivu account.");
    });
    if (value) {
      fetch(API + "/auth/verify-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: value }),
      }).then(async response => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail?.message || data.detail || "Verification failed");
        setMessage(data.message || "Email verified successfully.");
      }).catch(err => {
        setError(err instanceof Error ? err.message : "Verification failed");
        setMessage("");
      });
    }
    return () => window.cancelAnimationFrame(frame);
  }, []);

  async function resend(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(API + "/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail?.message || data.detail || "Could not send email");
      setMessage(data.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send email");
    } finally { setBusy(false); }
  }

  return <main className={styles.page}><header><Link href="/" className={styles.logo}><span>R</span> Rivu<span>ai</span></Link></header><section className={styles.card}><div className={styles.kicker}>RIVU / EMAIL SECURITY</div><h1>Verify your<br/><em>identity.</em></h1><p>{message}</p>{error && <div className={styles.error}>{error}</div>}{!token && <form className={styles.form} onSubmit={resend}><label className={styles.field}>Work email<input className={styles.input} type="email" value={email} onChange={e=>setEmail(e.target.value)} required placeholder="you@company.com"/></label><button className={styles.submit} disabled={busy}>{busy ? "Sending…" : "Resend verification email"}</button></form>}<p style={{marginTop:20,textAlign:"center",fontSize:12}}><Link href="/login" style={{color:"#a28eff"}}>Return to sign in</Link></p></section><footer className={styles.footer}>RIVU BY WATERTING · DATA REFINERY</footer></main>;
}
