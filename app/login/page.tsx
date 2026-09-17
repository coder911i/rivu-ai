"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, ShieldCheck, Sparkles } from "lucide-react";
import { api, saveSession } from "../../lib/api";
import { useRouter } from "next/navigation";
import styles from "./login.module.css";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [name, setName] = useState(""); const [username, setUsername] = useState("");
  const [error, setError] = useState(""); const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault(); setError(""); setLoading(true);
    try {
      const data = mode === "login" ? await api.login({ email, password }) : await api.signup({ email, username, password, full_name: name });
      saveSession(data); router.replace("/dashboard");
    } catch (err) { setError(err instanceof Error ? err.message : "Authentication failed"); }
    finally { setLoading(false); }
  }

  return <main className={styles.page}>
    <div className={styles.glow} />
    <div className={styles.shell}>
      <section className={styles.brandPane}>
        <div className={styles.brand}><span className={styles.mark}><i/><i/><i/><i/></span>Rivu<span>ai</span></div>
        <div className={styles.kicker}><Sparkles size={14}/> AI-NATIVE DATA REFINERY</div>
        <h1>Make messy data<br/><span>decision-ready.</span></h1>
        <p>One secure workspace to ingest, refine, validate and understand operational data.</p>
        <div className={styles.trust}><ShieldCheck size={17}/><span>Private workspace · auditable transformations · source preserved</span></div>
      </section>
      <section className={styles.formPane}>
        <div className={styles.switch}><button className={mode === "login" ? styles.active : ""} onClick={() => setMode("login")}>Sign in</button><button className={mode === "signup" ? styles.active : ""} onClick={() => setMode("signup")}>Create account</button></div>
        <h2>{mode === "login" ? "Welcome back." : "Create your workspace."}</h2>
        <p className={styles.sub}>{mode === "login" ? "Continue refining your data." : "Start with a private Rivu workspace."}</p>
        <form onSubmit={submit}>
          {mode === "signup" && <><label>Full name<input value={name} onChange={e => setName(e.target.value)} required placeholder="Your name" /></label><label>Username<input value={username} onChange={e => setUsername(e.target.value)} required placeholder="workspace handle" /></label></>}
          <label>Work email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="you@company.com" /></label>
          <label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} placeholder="••••••••" /></label>
          {error && <div className={styles.error}>{error}</div>}
          <button className={styles.submit} disabled={loading}>{loading ? "Authenticating…" : mode === "login" ? "Enter Rivu" : "Create workspace"}<ArrowRight size={17}/></button>
        </form>
        <small className={styles.legal}>By continuing, you agree to your organization&apos;s Rivu data policies.</small>
      </section>
    </div>
  </main>;
}
