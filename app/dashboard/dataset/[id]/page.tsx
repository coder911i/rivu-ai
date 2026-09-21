"use client";
import { useCallback, useEffect,useRef,useState, type ReactNode } from "react";
import { ArrowLeft, BrainCircuit, CheckCircle2, Download, Loader2, ShieldCheck, Sparkles, Table2, WandSparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import styles from "./dataset.module.css";
import { authFetch } from "../../../../lib/api";
import BrandLogo from "../../../../lib/BrandLogo";
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
type ArtifactMap=Record<string,{filename:string;download_url:string;size_bytes?:number}>;
type IntelligenceReport={ai?:{headline:string;summary:string;strengths:string[];risks:string[];actions:string[];data_readiness:number};quality:{overall:number;completeness:number;validity:number;consistency:number;uniqueness:number;integrity:number};issues:any[];sample_rows:Record<string,unknown>[];artifacts?:ArtifactMap;refinement?:{applied:number;failed:number;quality_delta:number}|null};

function apiErrorMessage(data: any, fallback: string): string {
  const detail = data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object") {
    if (typeof detail.message === "string" && detail.message.trim()) return detail.message;
    if (typeof detail.error === "string" && detail.error.trim()) return detail.error;
    try { return JSON.stringify(detail); } catch { return fallback; }
  }
  if (typeof data?.message === "string" && data.message.trim()) return data.message;
  return fallback;
}

export default function DatasetPage({params}:{params:Promise<{id:string}>}){
 const router=useRouter();
 const [datasetId,setDatasetId]=useState("");
 const [profile,setProfile]=useState<DatasetProfile|null>(null),[quality,setQuality]=useState<QualityReport|null>(null),[plan,setPlan]=useState<RefineryPlan|null>(null),[busy,setBusy]=useState(false),[preview,setPreview]=useState<PreviewResponse|null>(null),[running,setRunning]=useState(false),[autoRefining,setAutoRefining]=useState(false),[error,setError]=useState(""),[artifacts,setArtifacts]=useState<ArtifactMap|null>(null),[reportData,setReportData]=useState<IntelligenceReport|null>(null);
 const autoRefineStarted=useRef(false);
 const load = useCallback(async () => {
  if (!datasetId) return false;
  try{
    const [p,q]=await Promise.all([
      authFetch("/datasets/"+datasetId+"/profile",{headers:authHeaders()}),
      authFetch("/datasets/"+datasetId+"/quality",{headers:authHeaders()})
    ]);
    if(p.status===401||q.status===401){router.push("/login");return false}
    if(!p.ok){const d=await p.json().catch(()=>null);throw new Error(apiErrorMessage(d,"Profile unavailable"))}
    if(p.status===202||q.status===202){
      setError("Rivu is still processing this dataset…");
      return false;
    }
    const pd=await p.json();
    setProfile(pd);
    if(q.ok){setQuality(await q.json());await loadReport();}
    else throw new Error(await q.text().catch(()=> "Quality analysis unavailable")); 
    return true;
  }catch(e){setError(e instanceof Error?e.message:"Unable to load dataset intelligence.");return false}
 }, [datasetId, router]);
 async function loadReport(){if(!datasetId)return;try{const r=await authFetch("/reports/"+datasetId+"/dashboard",{headers:authHeaders()});const d=await r.json();if(r.ok){setReportData(d);if(d.artifacts)setArtifacts(d.artifacts)}}catch{}}
 useEffect(()=>{
  let cancelled=false;
  params.then(({id})=>{ if(!cancelled) setDatasetId(id); });
  return()=>{cancelled=true};
 }, [params]);
 useEffect(()=>{
  let cancelled=false;
  const poll=async()=>{
    const ready=await load();
    if(!ready&&!cancelled)setTimeout(poll,1800);
  };
  poll();
  return()=>{cancelled=true};
},[load]);
 useEffect(()=>{
  if(profile && quality && profile.dataset.status !== "transformed" && !autoRefineStarted.current && !autoRefining && !plan) {
    autoRefine();
  }
 },[profile,quality,plan,autoRefining,datasetId]);
 async function autoRefine() {
  if (!datasetId || autoRefineStarted.current || autoRefining) return;
  autoRefineStarted.current=true;
  setAutoRefining(true);
  setBusy(true);
  setError("");
  try {
    // Rivu's upload flow is a refinery: once profiling is complete, generate,
    // approve, and execute the AI plan against a new immutable dataset version.
    const planResponse=await authFetch("/datasets/"+datasetId+"/ai-plan",{
      method:"POST",headers:authHeaders()
    });
    const planData=await planResponse.json().catch(()=>({}));
    if(!planResponse.ok) throw new Error(apiErrorMessage(planData,"AI refinement plan failed"));
    if(!planData.id || !Array.isArray(planData.operations)){
      throw new Error("Rivu returned an invalid refinement plan.");
    }
    setPlan(planData);
    if(planData.operations.length===0){
      setError("✓ Dataset is already clean enough — no safe transformations were required. Your report is ready.");
      return;
    }

    const approval=await authFetch("/datasets/"+datasetId+"/transform/approve",{
      method:"POST",headers:{...authHeaders(),"Content-Type":"application/json"},
      body:JSON.stringify({plan_id:planData.id})
    });
    const approvalData=await approval.json().catch(()=>({}));
    if(!approval.ok) throw new Error(apiErrorMessage(approvalData,"Refinement approval failed"));

    const execution=await authFetch("/datasets/"+datasetId+"/transform/execute",{
      method:"POST",headers:{...authHeaders(),"Content-Type":"application/json"},
      body:JSON.stringify({plan_id:planData.id})
    });
    const executionData=await execution.json().catch(()=>({}));
    if(!execution.ok) throw new Error(apiErrorMessage(executionData,"Data refinement failed"));

    setArtifacts(executionData.artifacts||null);
    setError("✓ Data cleaned successfully — refined v"+executionData.version.number+" created. Your report is ready.");
    await load();
    await loadReport();
  } catch(error) {
    setError(error instanceof Error?error.message:"Automatic refinement failed. You can retry with AI Refinery Plan.");
    autoRefineStarted.current=false;
  } finally {
    setBusy(false);
    setAutoRefining(false);
  }
 }

 async function ai() {
  setBusy(true);
  setError("");

  try {
    const response = await fetch(
      API + "/datasets/" + datasetId + "/ai-plan",
      {
        method: "POST",
        headers: authHeaders(),
      }
    );

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(apiErrorMessage(data, "AI plan failed"));
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
    const r = await authFetch("/datasets/" + datasetId + "/transform/preview", {
      method: "POST", headers: {...authHeaders(), "Content-Type":"application/json"},
      body: JSON.stringify({plan_id: plan.id})
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(apiErrorMessage(d, "Preview failed"));
    setPreview(d);
  } catch (error) {
    setError(error instanceof Error ? error.message : "Preview failed");
  } finally { setBusy(false); }
 }

 async function executePlan() {
  if (!plan?.id || !window.confirm("Execute this approved refinement plan and create a new dataset version?")) return;
  setRunning(true); setError("");
  try {
    const approval = await authFetch("/datasets/" + datasetId + "/transform/approve", {
      method: "POST", headers: {...authHeaders(), "Content-Type":"application/json"},
      body: JSON.stringify({plan_id: plan.id})
    });
    const approvalData = await approval.json().catch(() => ({}));
    if (!approval.ok) throw new Error(apiErrorMessage(approvalData, "Plan approval failed"));

    const r = await authFetch("/datasets/" + datasetId + "/transform/execute", {
      method: "POST", headers: {...authHeaders(), "Content-Type":"application/json"},
      body: JSON.stringify({plan_id: plan.id})
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(apiErrorMessage(d, "Transformation failed"));
    setArtifacts(d.artifacts||null);
    setError("Transformation complete. New version v" + d.version.number + " created.");
    await load();
  } catch (error) {
    setError(error instanceof Error ? error.message : "Transformation failed");
  } finally { setRunning(false); }
 }

 async function report() {
  try {
    const response = await authFetch("/reports/" + datasetId + "/pdf", { headers: authHeaders() });
    if (!response.ok) throw new Error("Could not generate report");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "rivu-report-" + datasetId + ".pdf";
    a.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    setError(error instanceof Error ? error.message : "Could not generate report");
  }
 }
 return (
  <main className={styles.page}>
   <header>
    <div className={styles.headerLeft}><a href="/dashboard"><ArrowLeft size={16}/> Workspace</a><BrandLogo href="/dashboard" className={styles.datasetLogo}/></div>
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
     {artifacts&&<section className={styles.downloadPanel}><div><small>REFINED DATA / READY TO USE</small><h3>Your cleaned dataset is ready.</h3><p>Download the refined output in the original format or any supported analysis format.</p></div><div className={styles.downloadGrid}>
      {["csv","xlsx","json","parquet"].map((key)=>
       artifacts[key]&&<a key={key} href={artifacts[key].download_url} download={artifacts[key].filename} className={styles.ai}>
        <Download size={14}/> {key.toUpperCase()}
       </a>
      )}
      {artifacts["schema.json"]&&<a href={artifacts["schema.json"].download_url} download={artifacts["schema.json"].filename} className={styles.ai}>
       <Download size={14}/> SCHEMA
      </a>}
     </div></section>}

     <div className={styles.scoreRow}>
      <div className={styles.score}><small>DATA HEALTH</small><b>{profile.version.quality_score??"—"}</b><span>/ 100</span></div>
      <Stat label="Rows" value={profile.profile.row_count.toLocaleString()}/>
      <Stat label="Columns" value={profile.profile.column_count}/>
      <Stat label="Duplicates" value={profile.profile.duplicate_row_count}/>
      <Stat label="Null rate" value={profile.profile.total_null_pct+"%"}/>
     </div>

     <section className={styles.reportPanel}>
      <div className={styles.panelHead}><div><small>EXECUTIVE DATA REPORT</small><h2>{reportData?.ai?.headline||"Rivu intelligence report"}</h2></div><Sparkles size={18}/></div>
      <p className={styles.reportSummary}>{reportData?.ai?.summary||"Rivu is generating the measured report from the refined dataset."}</p>
      {reportData?.ai&&<div className={styles.aiReportGrid}><ReportList title="Strengths" items={reportData.ai.strengths}/><ReportList title="Risks" items={reportData.ai.risks}/><ReportList title="Recommended actions" items={reportData.ai.actions}/></div>}
      <div className={styles.reportScoreRow}><div><small>DATA READINESS</small><b>{Math.round(reportData?.ai?.data_readiness||Number(profile.version.quality_score||0))}</b>/100</div><div><small>QUALITY</small><b>{reportData?.quality?.overall?.toFixed(1)||profile.version.quality_score||"—"}</b></div><div><small>ISSUES</small><b>{reportData?.issues?.length||0}</b></div></div>
     </section>
     {reportData?.sample_rows?.length?<section className={styles.panel}>
      <div className={styles.panelHead}><div><small>CLEANED OUTPUT</small><h2>What the refined data looks like</h2></div><Table2 size={18}/></div>
      <div className={styles.previewTable}><div className={styles.previewRow}>{Object.keys(reportData.sample_rows[0]).map(k=><b key={k}>{k}</b>)}</div>{reportData.sample_rows.slice(0,12).map((row,i)=><div className={styles.previewRow} key={i}>{Object.keys(reportData.sample_rows[0]).map(k=><span key={k}>{String(row[k]??"")}</span>)}</div>)}</div>
     </section>:null}
     <section className={styles.analytics}>
      <div className={styles.panelHead}><div><small>RIVU ANALYTICS / POWER VIEW</small><h2>Data health at a glance</h2></div><Sparkles size={18}/></div>
      <div className={styles.analyticsGrid}>
       <div className={styles.chartCard}>
        <div className={styles.chartTitle}><span>QUALITY DIMENSIONS</span><b>{reportData?.quality?.overall?.toFixed(1)||Number(profile.version.quality_score||0).toFixed(1)}/100</b></div>
        <div className={styles.bars}>
         {reportData?.quality ? Object.entries(reportData.quality).filter(([k])=>k!=="overall").map(([k,v])=><div className={styles.chartBar} key={k}><span>{k}</span><i><em style={{width:Math.max(0,Math.min(100,Number(v)))+"%"}}/></i><b>{Number(v).toFixed(0)}</b></div>) : null}
        </div>
       </div>
       <div className={styles.chartCard}>
        <div className={styles.chartTitle}><span>ISSUE MIX</span><b>{reportData?.issues?.length||0} detected</b></div>
        <div className={styles.issueBars}>
         {["critical","high","medium","low"].map(level=>{const n=reportData?.issues?.filter((x:any)=>String(x.severity||"").toLowerCase()===level).length||0;const total=Math.max(1,reportData?.issues?.length||0);return <div key={level}><span>{level}</span><i><em style={{width:(n/total*100)+"%"}}/></i><b>{n}</b></div>})}
        </div>
        <div className={styles.analyticsNote}>Measured from the current refined version. No synthetic metrics.</div>
       </div>
       <div className={styles.chartCard}>
        <div className={styles.chartTitle}><span>REFINEMENT IMPACT</span><b>{reportData?.refinement?.quality_delta!==undefined?((reportData.refinement.quality_delta>0?"+":"")+Number(reportData.refinement.quality_delta).toFixed(1)):"—"}</b></div>
        <div className={styles.impact}><div><small>QUALITY BEFORE</small><strong>{reportData?.refinement?.quality_before!==undefined?Number(reportData.refinement.quality_before).toFixed(1):"—"}</strong></div><div className={styles.impactArrow}>→</div><div><small>QUALITY AFTER</small><strong>{reportData?.quality?.overall?.toFixed(1)||"—"}</strong></div></div>
        <div className={styles.analyticsNote}>{reportData?.refinement?reportData.refinement.applied+" operations applied · "+reportData.refinement.failed+" failed":"Refinement history will appear after a transformation."}</div>
       </div>
      </div>
     </section>

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
function ReportList({title,items}:{title:string;items:string[]}){return <div><h4>{title}</h4>{items?.slice(0,4).map((x,i)=><p key={i}>• {x}</p>)}</div>}
