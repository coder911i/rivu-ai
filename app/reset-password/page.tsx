"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import styles from "../login/login.module.css";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") || "");
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const path = token ? "/auth/password-reset/complete" : "/auth/password-reset/request";
      const body = token ? { token, new_password: password } : { email };
      const response = await fetch(API + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail?.message || data.detail || "Request failed");
      setMessage(data.message || "Request completed.");
      if (token) setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally { setBusy(false); }
  }

  return <main className={styles.page}><header><Link href="/" className={styles.logo}><span>R</span> Rivu<span>ai</span></Link></header><section className={styles.card}><div className={styles.kicker}>RIVU / ACCOUNT RECOVERY</div><h1>{token ? <>Choose a new<br/><em>password.</em></> : <>Recover your<br/><em>account.</em></>}</h1><p>{token ? "Use a strong password with uppercase, lowercase, and a number." : "We’ll email a secure, time-limited password reset link if the account exists."}</p><form className={styles.form} onSubmit={submit}>{token ? <label className={styles.field}>New password<input className={styles.input} type="password" value={password} onChange={e=>setPassword(e.target.value)} minLength={8} maxLength={128} required placeholder="At least 8 characters"/></label> : <label className={styles.field}>Work email<input className={styles.input} type="email" value={email} onChange={e=>setEmail(e.target.value)} required placeholder="you@company.com"/></label>}{error && <div className={styles.error}>{error}</div>}{message && <div className={styles.note}>{message}</div>}<button className={styles.submit} disabled={busy}>{busy ? "Please wait…" : token ? "Update password" : "Send reset link"}</button></form><p style={{marginTop:20,textAlign:"center",fontSize:12}}><Link href="/login" style={{color:"#a28eff"}}>Return to sign in</Link></p></section><footer className={styles.footer}>RIVU BY WATERTING · DATA REFINERY</footer></main>;
}
