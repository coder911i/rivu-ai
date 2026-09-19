"use client";
import { ChangeEvent, useCallback, useEffect, useState, type ReactNode } from "react";
import { Activity, ArrowUpRight, Database, FileText, FolderPlus, LogOut, Plus, RefreshCw, ShieldCheck, Sparkles, UploadCloud, X } from "lucide-react";
import styles from "./dashboard.module.css";
import { authFetch } from "../../lib/api";
import BrandLogo from "../../lib/BrandLogo";

const API=process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000/api/v1";
type Project={id:string;name:string;description?:string;dataset_count:number;color:string};
type Dataset={id:string;name:string;original_filename:string;file_format:string;status:string;current_version:number;created_at:string};
const authHeaders=()=>({Authorization:"Bearer "+(typeof window!=="undefined"?localStorage.getItem("rivu_access_token")||"":"")});

export default function Dashboard(){
 const [projects,setProjects]=useState<Project[]>([]);const [selected,setSelected]=useState<Project|null>(null);const [datasets,setDatasets]=useState<Dataset[]>([]);const [loading,setLoading]=useState(true);const [error,setError]=useState("");const [showNew,setShowNew]=useState(false);const [name,setName]=useState("");const [uploading,setUploading]=useState(false);const [message,setMessage]=useState("");
 const selectProject = useCallback(async (p:Project) => {
  setSelected(p);
  try{
    const r=await authFetch("/projects/"+p.id,{headers:authHeaders()});
    if(r.status===401){location.href="/login";return}
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail?.message||d.detail||"Could not load project");
    setDatasets(d.datasets||[]);
  }catch(e){setError(e instanceof Error?e.message:"Could not load project.")}
 }, []);
 async function load(){setLoading(true);try{const r=await authFetch("/projects/",{headers:authHeaders()});if(r.status===401){location.href="/login";return}const d=await r.json();setProjects(d.projects||[]);if(!selected&&d.projects?.[0])selectProject(d.projects[0]);}catch{setError("Could not reach Rivu API.")}finally{setLoading(false)}}
 useEffect(()=>{let cancelled=false;async function loadInitial(){try{const r=await authFetch("/projects/",{headers:authHeaders()});if(r.status===401){location.href="/login";return}const d=await r.json();if(cancelled)return;const list:Project[]=d.projects||[];setProjects(list);const first=list[0];if(first){setSelected(first);const detail=await authFetch("/projects/"+first.id,{headers:authHeaders()});if(detail.status===401){location.href="/login";return}const projectData=await detail.json();if(!cancelled)setDatasets(projectData.datasets||[])}}catch{if(!cancelled)setError("Could not reach Rivu API.")}finally{if(!cancelled)setLoading(false)}}void loadInitial();return()=>{cancelled=true}},[]);
 async function create(){if(!name.trim())return;const r=await authFetch("/projects/",{method:"POST",headers:{...authHeaders(),"Content-Type":"application/json"},body:JSON.stringify({name})});if(r.ok){setName("");setShowNew(false);await load()}else{const d=await r.json().catch(()=>({}));setError(d.detail?.message||d.detail||"Project could not be created.")}}
 async function upload(e:ChangeEvent<HTMLInputElement>){const f=e.target.files?.[0];if(!f||!selected)return;setUploading(true);setMessage("Uploading and profiling…");const fd=new FormData();fd.append("file",f);fd.append("name",f.name.replace(/\.[^.]+$/,""));try{const r=await authFetch("/datasets/projects/"+selected.id+"/upload",{method:"POST",headers:authHeaders(),body:fd});const d=await r.json();if(!r.ok)throw new Error(d.detail?.message||d.detail||"Upload failed");setMessage("Uploaded. Rivu is profiling the dataset…");
    await selectProject(selected);
    // Refresh while the background profiler is running so the UI reflects the real status.
    let attempts=0;
    const poll=async()=>{attempts++; await selectProject(selected); if(attempts<20){setTimeout(poll,1500)}else{setMessage("Processing is taking longer than usual. You can open the dataset when it is ready.")}};
    setTimeout(poll,1200)}catch(e){setMessage(e instanceof Error?e.message:"Upload failed")}finally{setUploading(false);e.target.value=""}}
 async function downloadReport(datasetId:string, datasetName:string){
  try{
   const r=await authFetch("/reports/"+datasetId+"/pdf",{headers:authHeaders()});
   if(!r.ok){const d=await r.json().catch(()=>null);throw new Error(typeof d?.detail==="string"?d.detail:d?.detail?.message||"Could not generate report")}
   const blob=await r.blob(); const url=URL.createObjectURL(blob); const a=document.createElement("a");
   a.href=url; a.download="rivu-report-"+datasetName.replace(/[^a-z0-9_-]+/gi,"-")+".pdf"; a.click(); URL.revokeObjectURL(url);
  }catch(e){setError(e instanceof Error?e.message:"Could not generate report")}
 }
 function logout(){localStorage.clear();location.href="/login"}
 return <main className={styles.app}><aside><BrandLogo href="/" className={styles.brand}/><div className={styles.nav}><a className={styles.active} href="#overview"><Activity size={17}/>Overview</a><a href="#datasets"><Database size={17}/>Datasets</a><a href="#ai-intelligence"><Sparkles size={17}/>AI Intelligence</a><a href="#reports"><FileText size={17}/>Reports</a><a href="#security"><ShieldCheck size={17}/>Security</a></div><button className={styles.logout} onClick={logout}><LogOut size={16}/>Sign out</button></aside>
 <section className={styles.main} id="overview"><header><div><div className={styles.eyebrow}>WORKSPACE / DATA INTELLIGENCE</div><h1>Good data starts here.</h1><p>Refine messy information into a verified intelligence layer.</p></div><div className={styles.headerActions}><button onClick={load}><RefreshCw size={15}/></button><button className={styles.primary} onClick={()=>setShowNew(true)}><Plus size={16}/> New project</button></div></header>
 {error&&<div className={styles.error}>{error}</div>}<div className={styles.metrics}><Metric icon={<Database/>} label="Projects" value={projects.length}/><Metric icon={<FileText/>} label="Datasets" value={projects.reduce((a,p)=>a+p.dataset_count,0)}/><Metric icon={<Sparkles/>} label="AI refinery" value="Ready"/><Metric icon={<ShieldCheck/>} label="Workspace" value="Protected"/></div>
 <div id="datasets" className={styles.body}><div className={styles.projects}><div className={styles.sectionHead}><h2>Projects</h2><span>{projects.length} total</span></div>{loading?<div className={styles.empty}>Loading workspace…</div>:projects.map(p=><button className={selected?.id===p.id?styles.projectSelected:styles.project} key={p.id} onClick={()=>selectProject(p)}><span className={styles.projectIcon} style={{background:p.color||"#6d5ce7"}}>R</span><span><b>{p.name}</b><small>{p.dataset_count} datasets</small></span><ArrowUpRight size={15}/></button>)}{!projects.length&&!loading&&<div className={styles.empty}>Create your first data project.</div>}</div>
 <div className={styles.datasets}><div className={styles.sectionHead}><div><h2>{selected?selected.name:"Select a project"}</h2><span>{selected?"DATA REFINERY":"No project selected"}</span></div>{selected&&<label className={styles.upload}><UploadCloud size={17}/>{uploading?"Uploading…":"Add data"}<input type="file" accept=".csv,.json,.xlsx,.xls,.parquet" onChange={upload} disabled={uploading}/></label>}</div>{message&&<div className={styles.message}>{message}</div>}{selected&&<div className={styles.drop}><UploadCloud size={28}/><b>Drop your dataset here</b><span>CSV · XLSX · JSON · Parquet</span>{selected&&<label>Browse files<input type="file" accept=".csv,.json,.xlsx,.xls,.parquet" onChange={upload}/></label>}</div>}<div className={styles.datasetList}>{datasets.map(d=><div className={styles.dataset} key={d.id}><span className={styles.fileIcon}><FileText size={17}/></span><div><b>{d.name}</b><small>{d.original_filename} · v{d.current_version}</small></div><em className={d.status==="profiled"?"ok":""}>{d.status}</em><button onClick={()=>location.href="/dashboard/dataset/"+d.id}>Open <ArrowUpRight size={13}/></button></div>)}</div></div></div>

 <section id="ai-intelligence" className={styles.dashboardSection}><div className={styles.sectionHead}><div><h2>AI Intelligence</h2><span>PROFILE · QUALITY · REFINEMENT</span></div><Sparkles size={17}/></div><div className={styles.featureGrid}>{datasets.length?datasets.map(d=><div className={styles.featureCard} key={"ai-"+d.id}><div><b>{d.name}</b><small>{d.file_format.toUpperCase()} · {d.status}</small></div><button onClick={()=>location.href="/dashboard/dataset/"+d.id}>Open intelligence <ArrowUpRight size={13}/></button></div>):<div className={styles.empty}>Upload a dataset to activate profiling and AI refinement.</div>}</div></section>
 <section id="reports" className={styles.dashboardSection}><div className={styles.sectionHead}><div><h2>Reports</h2><span>QUALITY REPORTS</span></div><FileText size={17}/></div><div className={styles.featureGrid}>{datasets.length?datasets.map(d=><div className={styles.featureCard} key={"report-"+d.id}><div><b>{d.name}</b><small>Generate the current quality report</small></div><button onClick={()=>downloadReport(d.id,d.name)}>Download PDF</button></div>):<div className={styles.empty}>Reports will appear after a dataset is uploaded.</div>}</div></section>
 <section id="security" className={styles.dashboardSection}><div className={styles.sectionHead}><div><h2>Security</h2><span>WORKSPACE PROTECTION</span></div><ShieldCheck size={17}/></div><div className={styles.securityGrid}><div className={styles.securityCard}><ShieldCheck size={18}/><b>Authenticated workspace</b><small>JWT authentication is required for workspace and dataset operations.</small></div><div className={styles.securityCard}><Database size={18}/><b>Tenant-isolated data</b><small>Projects, datasets and reports are scoped to the authenticated organization.</small></div><div className={styles.securityCard}><Sparkles size={18}/><b>Controlled transformations</b><small>AI creates an allowlisted plan; the deterministic engine performs the actual data changes.</small></div></div></section>
 {showNew&&<div className={styles.modal}><div className={styles.modalCard}><button className={styles.close} onClick={()=>setShowNew(false)}><X/></button><div className={styles.eyebrow}>NEW PROJECT</div><h2>Create a data workspace.</h2><p>Projects keep sources, transformations and quality history isolated.</p><input value={name} onChange={e=>setName(e.target.value)} placeholder="e.g. Customer Data Refinery" onKeyDown={e=>e.key==="Enter"&&create()}/><button className={styles.primaryWide} onClick={create}><FolderPlus size={17}/> Create project</button></div></div>}
 </section></main>
}
function Metric({icon,label,value}:{icon:ReactNode;label:string;value:string|number}){return <div className={styles.metric}><span>{icon}</span><small>{label}</small><b>{value}</b></div>}
