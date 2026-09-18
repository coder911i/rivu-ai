"use client";
import { useEffect,useState } from "react";
import { ArrowLeft, BrainCircuit, CheckCircle2, Download, Loader2, ShieldCheck, Sparkles, Table2, WandSparkles } from "lucide-react";
import styles from "./dataset.module.css";
const API=process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000/api/v1";
export default function DatasetPage({params}:{params:{id:string}}){
 const [profile,setProfile]=useState<any>(null),[quality,setQuality]=useState<any>(null),[plan,setPlan]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
 const h=()=>({Authorization:"Bearer "+(typeof window!=="undefined"?localStorage.getItem("rivu_access_token")||"":"")});
 async function load(){try{const [p,q]=await Promise.all([fetch(API+"/datasets/"+params.id+"/profile",{headers:h()}),fetch(API+"/datasets/"+params.id+"/quality",{headers:h()})]);if(p.ok)setProfile(await p.json());if(q.ok)setQuality(await q.json());}catch{setError("Unable to load dataset intelligence.")}}
 useEffect(()=>{load()},[]);
 async function ai() {
  setBusy(true);
  setError("");

  try {
    const response = await fetch(
      API + "/datasets/" + params.id + "/ai-plan",
      {
        method: "POST",
        headers: h(),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "AI plan failed");
    }

    setPlan(data);
  } catch (error) {
    setError(
      error instanceof Error ? error.message : "AI plan failed"
    );
  } finally {
    setBusy(false);
  }
 }
 async function report() {
  try {
    const response = await fetch(API + "/reports/" + params.id + "/json", { headers: h() });
    if (!response.ok) throw new Error("Could not generate report");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "rivu-report-" + params.id + ".json";
    a.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    setError(error instanceof Error ? error.message : "Could not generate report");
  }
 }
 return <main className={styles.page}><header><a href="/dashboard"><ArrowLeft size={16}/> Workspace</a><div className={styles.secure}><ShieldCheck size={15}/> Tenant-isolated data</div></header>
 {!profile?<div className={styles.loading}><Loader2 className={styles.spin}/><h2>Refining your dataset…</h2><p>Rivu is profiling structure, quality and consistency.</p><button onClick={load}>Refresh</button></div>:
 <><div className={styles.hero}><div><div className={styles.kicker}>DATASET / {profile.dataset.status?.toUpperCase()}</div><h1>{profile.dataset.name}</h1><p>{profile.profile.row_count.toLocaleString()} rows · {profile.profile.column_count} columns · v{profile.version.number}</p></div><div className={styles.actions}><button onClick={report}><Download size={15}/> Report</button><button className={styles.ai} onClick={ai} disabled={busy}>{busy?<Loader2 className={styles.spin}/>:<WandSparkles size={15}/>} {busy?"Analyzing…":"AI Refinery Plan"}</button></div></div>
 {error&&<div className={styles.error}>{error}</div>}
 <div className={styles.scoreRow}><div className={styles.score}><small>DATA HEALTH</small><b>{profile.version.quality_score??"—"}</b><span>/ 100</span></div><Stat label="Rows" value={profile.profile.row_count.toLocaleString()}/><Stat label="Columns" value={profile.profile.column_count}/><Stat label="Duplicates" value={profile.profile.duplicate_row_count}/><Stat label="Null rate" value={profile.profile.total_null_pct+"%"}/></div>
 <section className={styles.grid}><div className={styles.panel}><div className={styles.panelHead}><div><small>SCHEMA INTELLIGENCE</small><h2>Columns</h2></div><Table2 size={18}/></div><div className={styles.table}>{profile.columns.map((c:any)=><div className={styles.row} key={c.name}><b>{c.name}</b><span>{c.semantic_type}</span><span>{c.null_pct}% null</span><span>{c.uniqueness_pct}% unique</span></div>)}</div></div>
 <div className={styles.panel}><div className={styles.panelHead}><div><small>QUALITY INTELLIGENCE</small><h2>{quality?quality.overall_score:"—"} / 100</h2></div><BrainCircuit size={18}/></div>{quality?<div className={styles.quality}>{Object.entries(quality.scores).map(([k,v]:any)=><div key={k}><span>{k}</span><div><i style={{width:Math.min(100,Number(v))+"%"}}/></div><b>{Number(v).toFixed(1)}</b></div>)}<div className={styles.issues}><strong>{quality.counts.total} issues detected</strong>{quality.issues.slice(0,5).map((i:any)=><p key={i.id}><span>{i.severity}</span>{i.title}</p>)}</div></div>:<p className={styles.muted}>Quality analysis is still running.</p>}</div></section>
 {plan&&<section className={styles.plan}><div className={styles.panelHead}><div><small>RIVU AI</small><h2>Recommended refinement plan</h2></div><Sparkles size={19}/></div><p className={styles.summary}>{plan.summary||plan.dataset_summary}</p><div className={styles.ops}>{plan.operations?.map((o:any,i:number)=><div key={i}><CheckCircle2 size={16}/><b>{o.type.replaceAll("_"," ")}</b><span>{o.column||"dataset"} · {Math.round(o.confidence*100)}% confidence</span><p>{o.reason}</p></div>)}</div></section>}</section></>}
 </main>
}
function Stat({label,value}:{label:string,value:any}){return <div className={styles.stat}><small>{label}</small><b>{value}</b></div>}
