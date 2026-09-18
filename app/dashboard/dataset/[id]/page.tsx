"use client";
import { useCallback, useEffect,useState, type ReactNode } from "react";
import { ArrowLeft, BrainCircuit, CheckCircle2, Download, Loader2, ShieldCheck, Sparkles, Table2, WandSparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import styles from "./dataset.module.css";
import { authFetch } from "../../../../lib/api";
const API=process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000/api/v1";
const authHeaders=()=>({Authorization:"Bearer "+(typeof window!=="undefined"?localStorage.getItem("rivu_access_token")||"":"")});

type ColumnProfile={name:string;semantic_type:string;null_pct:number|string;uniqueness_pct:number|string};
type DatasetProfile={dataset:{status?:string;name:string};profile:{row_count:number;column_count:number;duplicate_row_count:number;total_null_pct:number|string};version:{number:number;quality_score?:number|string|null};columns:ColumnProfile[]};
type QualityIssue={id:string;severity:string;title:string};
type QualityReport={overall_score:number|string;scores:Record<string,number|string>;counts:{total:number};issues:QualityIssue[]};
type PlanOperation={type:string;column?:string;confidence:number;reason?:string};
type RefineryPlan={id?:string;summary?:string;dataset_summary?:string;operations?:PlanOperation[]};
type PreviewItem={column?:string;op?:string;before?:unknown[];after?:unknown[]};
type PreviewResponse={previews?:PreviewItem[]};

export default function DatasetPage({params}:{params:{id:string}}){
 const router=useRouter();
 const [profile,setProfile]=useState<DatasetProfile|null>(null),[quality,setQuality]=useState<QualityReport|null>(null),[plan,setPlan]=useState<RefineryPlan|null>(null),[busy,setBusy]=useState(false),[preview,setPreview]=useState<PreviewResponse|null>(null),[running,setRunning]=useState(false),[error,setError]=useState("");
 const load = useCallback(async () => {
  try{
    const [p,q]=await Promise.all([
      authFetch("/datasets/"+params.id+"/profile",{headers:authHeaders()}),
      authFetch("/datasets/"+params.id+"/quality",{headers:authHeaders()})
    ]);
    if(p.status===401||q.status===401){router.push("/login");return}
    if(p.status===202||q.status===202){
      setError("Rivu is still processing this dataset…");
      return false;
    }
    if(!p.ok){const d=await p.json().catch(()=>({}));throw new Error(d.detail?.message||d.detail||"Profile unavailable")}
    const pd=await p.json();
    setProfile(pd);
    if(q.ok)setQuality(await q.json());
    return true;
  }catch(e){setError(e instanceof Error?e.message:"Unable to load dataset intelligence.");return false}
 }, [params.id, router]);
 useEffect(()=>{
  let cancelled=false;
  const poll=async()=>{
    const ready=await load();
    if(!ready&&!cancelled)setTimeout(poll,1800);
  };
  poll();
  return()=>{cancelled=true};
},[load]);
 async function ai() {
  setBusy(true);
  setError("");

  try {
    const response = await fetch(
      API + "/datasets/" + params.id + "/ai-plan",
      {
        method: "POST",
        headers: authHeaders(),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail?.message || data.detail || "AI plan failed");
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
 async function previewPlan() {
  if (!plan?.id) return;
  setBusy(true); setError("");
  try {
    const r = await authFetch("/datasets/" + params.id + "/transform/preview", {
      method: "POST", headers: {...authHeaders(), "Content-Type":"application/json"},
      body: JSON.stringify({plan_id: plan.id})
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail?.message || d.detail || "Preview failed");
    setPreview(d);
  } catch (error) {
    setError(error instanceof Error ? error.message : "Preview failed");
  } finally { setBusy(false); }
 }

 async function executePlan() {
  if (!plan?.id || !window.confirm("Execute this approved refinement plan and create a new dataset version?")) return;
  setRunning(true); setError("");
  try {
    const r = await authFetch("/datasets/" + params.id + "/transform/execute", {
      method: "POST", headers: {...authHeaders(), "Content-Type":"application/json"},
      body: JSON.stringify({plan_id: plan.id})
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail?.message || d.detail || "Transformation failed");
    setError("Transformation complete. New version v" + d.version.number + " created.");
    await load();
  } catch (error) {
    setError(error instanceof Error ? error.message : "Transformation failed");
  } finally { setRunning(false); }
 }

 async function report() {
  try {
    const response = await authFetch("/reports/" + params.id + "/json", { headers: authHeaders() });
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
 return (
  <main className={styles.page}>
   <header>
    <a href="/dashboard"><ArrowLeft size={16}/> Workspace</a>
    <div className={styles.secure}><ShieldCheck size={15}/> Tenant-isolated data</div>
   </header>

   {!profile ? (
    <div className={styles.loading}>
     <Loader2 className={styles.spin}/>
     <h2>Refining your dataset...</h2>
     <p>Rivu is profiling structure, quality and consistency.</p>
     {error&&<div className={styles.error}>{error}</div>}
     <button onClick={load}>Refresh</button>
    </div>
   ) : (
    <>
     <div className={styles.hero}>
      <div>
       <div className={styles.kicker}>DATASET / {profile.dataset.status?.toUpperCase()}</div>
       <h1>{profile.dataset.name}</h1>
       <p>{profile.profile.row_count.toLocaleString()} rows · {profile.profile.column_count} columns · v{profile.version.number}</p>
      </div>
      <div className={styles.actions}>
       <button onClick={report}><Download size={15}/> Report</button>
       <button className={styles.ai} onClick={ai} disabled={busy}>
        {busy?<Loader2 className={styles.spin}/>:<WandSparkles size={15}/>} {busy?"Analyzing...":"AI Refinery Plan"}
       </button>
      </div>
     </div>

     {error&&<div className={styles.error}>{error}</div>}

     <div className={styles.scoreRow}>
      <div className={styles.score}><small>DATA HEALTH</small><b>{profile.version.quality_score??"—"}</b><span>/ 100</span></div>
      <Stat label="Rows" value={profile.profile.row_count.toLocaleString()}/>
      <Stat label="Columns" value={profile.profile.column_count}/>
      <Stat label="Duplicates" value={profile.profile.duplicate_row_count}/>
      <Stat label="Null rate" value={profile.profile.total_null_pct+"%"}/>
     </div>

     <section className={styles.grid}>
      <div className={styles.panel}>
       <div className={styles.panelHead}>
        <div><small>SCHEMA INTELLIGENCE</small><h2>Columns</h2></div>
        <Table2 size={18}/>
       </div>
       <div className={styles.table}>
        {profile.columns.map((c)=>(
         <div className={styles.row} key={c.name}>
          <b>{c.name}</b><span>{c.semantic_type}</span><span>{c.null_pct}% null</span><span>{c.uniqueness_pct}% unique</span>
         </div>
        ))}
       </div>
      </div>

      <div className={styles.panel}>
       <div className={styles.panelHead}>
        <div><small>QUALITY INTELLIGENCE</small><h2>{quality?quality.overall_score:"—"} / 100</h2></div>
        <BrainCircuit size={18}/>
       </div>
       {quality ? (
        <div className={styles.quality}>
         {Object.entries(quality.scores).map(([k,v])=>(
          <div key={k}><span>{k}</span><div><i style={{width:Math.min(100,Number(v))+"%"}}/></div><b>{Number(v).toFixed(1)}</b></div>
         ))}
         <div className={styles.issues}>
          <strong>{quality.counts.total} issues detected</strong>
          {quality.issues.slice(0,5).map((i)=><p key={i.id}><span>{i.severity}</span>{i.title}</p>)}
         </div>
        </div>
       ) : (
        <p className={styles.muted}>Quality analysis is still running.</p>
       )}
      </div>
     </section>

     {plan&&(
      <section className={styles.plan}>
       <div className={styles.panelHead}>
        <div><small>RIVU AI / CLEANING STUDIO</small><h2>Recommended refinement plan</h2></div>
        <Sparkles size={19}/>
       </div>
       <p className={styles.summary}>{plan.summary||plan.dataset_summary}</p>
       <div className={styles.ops}>
        {plan.operations?.map((o,i)=>(
         <div key={i}><CheckCircle2 size={16}/><b>{o.type.replaceAll("_"," ")}</b><span>{o.column||"dataset"} · {Math.round(o.confidence*100)}% confidence</span><p>{o.reason}</p></div>
        ))}
       </div>
       <div className={styles.actions}>
        <button onClick={previewPlan} disabled={busy}>Preview changes</button>
        <button className={styles.ai} onClick={executePlan} disabled={running}>{running?"Executing...":"Approve & refine"}</button>
       </div>
       {preview&&(
        <div className={styles.issues}>
         <strong>Before / after preview</strong>
         {preview.previews?.map((p,i)=>(
          <p key={i}><span>{p.column||p.op}</span>{(p.before||[]).slice(0,3).join(", ")} → {(p.after||[]).slice(0,3).join(", ")}</p>
         ))}
        </div>
       )}
      </section>
     )}
    </>
   )}
  </main>
 )
}
function Stat({label,value}:{label:string,value:ReactNode}){return <div className={styles.stat}><small>{label}</small><b>{value}</b></div>}
