"use client";

import { ChangeEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Activity, ArrowLeft, ArrowRight, CheckCircle2, ChevronDown, Database, Download, FileJson, FileSpreadsheet, FileUp, FolderKanban, Gauge, LoaderCircle, LockKeyhole, LogOut, Search, Settings2, ShieldCheck, Sparkles, WandSparkles, XCircle } from "lucide-react";
import { authFetch } from "../../lib/api";
import BrandLogo from "../../lib/BrandLogo";
import styles from "./services.module.css";

type Project = { id: string; name: string; dataset_count?: number };
type PlanOperation = { type: string; column?: string | null; confidence?: number; reason?: string };
type Plan = { id: string; summary?: string; dataset_summary?: string; detected_domain?: string; operations: PlanOperation[] };
type Artifact = { filename: string; download_url: string };
type DatasetProfile = { dataset?: { id: string; name: string; status: string }; profile?: { row_count: number; column_count: number; duplicate_row_count: number; total_null_pct: number }; version?: { number: number; quality_score?: number | null } };
type ApiError = { detail?: string | { message?: string; cause?: string; type?: string }; message?: string };

function messageFrom(data: ApiError, fallback: string) {
  if (typeof data?.detail === "string") return data.detail;
  if (data?.detail && typeof data.detail === "object" && typeof data.detail.message === "string") {
    const cause = typeof data.detail.cause === "string" ? data.detail.cause : "";
    return cause ? data.detail.message + " Details: " + cause : data.detail.message;
  }
  return data?.message || fallback;
}
async function jsonOrEmpty(response: Response): Promise<Record<string, unknown>> {
  return await response.json().catch(() => ({})) as Record<string, unknown>;
}

export default function ServicesPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [datasetId, setDatasetId] = useState("");
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [artifacts, setArtifacts] = useState<Record<string, Artifact> | null>(null);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("Ready");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [signedIn, setSignedIn] = useState(() => {
    if (typeof window !== "undefined") {
      return Boolean(localStorage.getItem("rivu_access_token"));
    }
    return false;
  });
  const [search, setSearch] = useState("");

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("rivu_access_token") : null;
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const response = await authFetch("/projects/");
        if (response.status === 401) { router.push("/login"); return; }
        const data = await jsonOrEmpty(response);
        if (!response.ok) throw new Error(messageFrom(data as ApiError, "Could not load projects."));
        if (!cancelled) {
          const list = (data.projects || []) as Project[];
          setProjects(list);
          if (list[0]) setProjectId(list[0].id);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not connect to Rivu.");
      }
    })();
    return () => { cancelled = true; };
  }, [router]);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] || null;
    setError(""); setNotice(""); setPlan(null); setPreview(null); setArtifacts(null); setProfile(null); setDatasetId("");
    if (!selected) { setFile(null); return; }
    const ext = selected.name.split(".").pop()?.toLowerCase() || "";
    if (!["csv", "json", "xlsx", "xls", "parquet"].includes(ext)) { setFile(null); setError("Use CSV, JSON, XLSX, XLS or Parquet files."); event.target.value = ""; return; }
    if (selected.size > 500 * 1024 * 1024) { setFile(null); setError("File exceeds the 500 MB limit."); event.target.value = ""; return; }
    if (!selected.size) { setFile(null); setError("This file is empty."); event.target.value = ""; return; }
    setFile(selected);
  }

  async function uploadAndProfile() {
    if (!file || !projectId || busy) return;
    setBusy(true); setError(""); setNotice(""); setStage("Uploading source data");
    try {
      const form = new FormData(); form.append("file", file); form.append("name", file.name.replace(/\.[^.]+$/, "").slice(0, 300));
      const uploadResponse = await authFetch("/datasets/projects/" + encodeURIComponent(projectId) + "/upload", { method: "POST", body: form });
      const uploaded = await jsonOrEmpty(uploadResponse);
      if (!uploadResponse.ok) throw new Error(messageFrom(uploaded as ApiError, "Upload failed."));
      const id = String((uploaded.dataset as { id?: string } | undefined)?.id || "");
      if (!id) throw new Error("Upload completed but the API did not return a dataset ID.");
      setDatasetId(id); setStage("Profiling structure and quality");
      let ready: DatasetProfile | null = null;
      for (let attempt = 0; attempt < 30; attempt++) {
        await new Promise(resolve => window.setTimeout(resolve, 1800));
        const [pResponse, qResponse] = await Promise.all([authFetch("/datasets/" + id + "/profile"), authFetch("/datasets/" + id + "/quality")]);
        if (pResponse.status === 401 || qResponse.status === 401) { router.push("/login"); return; }
        if (pResponse.ok && qResponse.ok) { ready = await jsonOrEmpty(pResponse) as DatasetProfile; await qResponse.json().catch(() => ({})); break; }
        if (pResponse.status >= 500) throw new Error(messageFrom(await jsonOrEmpty(pResponse) as ApiError, "Profiling failed."));
        if (qResponse.status >= 500) throw new Error(messageFrom(await jsonOrEmpty(qResponse) as ApiError, "Quality analysis failed."));
        const jobsResponse = await authFetch("/datasets/" + id + "/jobs");
        if (jobsResponse.ok) {
          const jobsData = await jsonOrEmpty(jobsResponse);
          const jobs = Array.isArray(jobsData.jobs) ? jobsData.jobs as Array<{type?: string; status?: string; progress?: number; message?: string; error?: string}> : [];
          const latest = jobs.find(job => job.type === "profile");
          if (latest?.status === "failed") throw new Error("Dataset processing failed: " + (latest.error || "The backend worker failed without an error message."));
          if (latest && (latest.status === "queued" || latest.status === "processing")) {
            setStage((latest.message || "Profiling dataset") + (typeof latest.progress === "number" ? " (" + latest.progress + "%)" : ""));
          }
        }
      }
      if (!ready) throw new Error("Profiling is taking longer than expected. Your upload is saved; retry in the dataset workspace.");
      setProfile(ready); setNotice("Profile ready. Generate a plan to inspect proposed changes."); setStage("Ready");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not upload and profile this file."); setStage("Ready"); }
    finally { setBusy(false); }
  }

  async function generatePlan() {
    if (!datasetId || busy) return;
    setBusy(true); setError(""); setStage("Building AI refinement plan");
    try {
      const response = await authFetch("/datasets/" + datasetId + "/ai-plan", { method: "POST" });
      const data = await jsonOrEmpty(response);
      if (!response.ok) throw new Error(messageFrom(data as ApiError, "AI plan generation failed."));
      setPlan(data as Plan); setPreview(null); setArtifacts(null); setNotice("Plan generated. Review every operation before execution.");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not generate a plan."); }
    finally { setBusy(false); setStage("Ready"); }
  }

  async function previewPlan() {
    if (!datasetId || !plan?.id || busy) return;
    setBusy(true); setError(""); setStage("Preparing transformation preview");
    try {
      const response = await authFetch("/datasets/" + datasetId + "/transform/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plan_id: plan.id }) });
      const data = await jsonOrEmpty(response);
      if (!response.ok) throw new Error(messageFrom(data as ApiError, "Preview failed."));
      setPreview(data); setNotice("Preview ready. The original dataset remains unchanged.");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not create preview."); }
    finally { setBusy(false); setStage("Ready"); }
  }

  async function executePlan() {
    if (!datasetId || !plan?.id || !preview || busy) return;
    if (!window.confirm("Apply this plan and create a new immutable dataset version? The source version will not be overwritten.")) return;
    setBusy(true); setError(""); setStage("Applying approved transformations");
    try {
      const headers = { "Content-Type": "application/json" }; const body = JSON.stringify({ plan_id: plan.id });
      const approval = await authFetch("/datasets/" + datasetId + "/transform/approve", { method: "POST", headers, body });
      const approved = await jsonOrEmpty(approval);
      if (!approval.ok) throw new Error(messageFrom(approved as ApiError, "Plan approval failed."));
      const response = await authFetch("/datasets/" + datasetId + "/transform/execute", { method: "POST", headers, body });
      const data = await jsonOrEmpty(response);
      if (!response.ok) throw new Error(messageFrom(data as ApiError, "Transformation failed."));
      setArtifacts((data.artifacts || null) as Record<string, Artifact> | null);
      setNotice("Transformation complete. A new version was created; the source remains preserved.");
    } catch (e) { setError(e instanceof Error ? e.message : "Transformation failed."); }
    finally { setBusy(false); setStage("Ready"); }
  }

  const filteredProjects = projects.filter(p => p.name.toLowerCase().includes(search.toLowerCase()));
  const profileStats = profile?.profile;
  return (
    <main className={styles.app}>
      <aside className={styles.sidebar}>
        <div className={styles.brandWrap}><BrandLogo href="/" className={styles.brand}/></div>
        <button className={styles.workspaceButton} onClick={() => router.push("/dashboard")}><span className={styles.workspaceIcon}><Database size={15}/></span><span><small>WORKSPACE</small><b>Rivu Data Lab</b></span><ChevronDown size={14}/></button>
        <div className={styles.navLabel}>WORKSPACE</div>
        <nav className={styles.nav}>
          <Link href="/dashboard"><Activity size={16}/> Overview</Link>
          <Link href="/dashboard#datasets"><Database size={16}/> Datasets</Link>
          <Link href="/dashboard#intelligence"><Sparkles size={16}/> Intelligence</Link>
          <Link href="/services" className={styles.active}><WandSparkles size={16}/> Data Studio <span className={styles.navBadge}>LIVE</span></Link>
          <Link href="/dashboard#reports"><FolderKanban size={16}/> Reports</Link>
        </nav>
        <div className={styles.sidebarBottom}>
          <div className={styles.sidebarStatus}><span/> All systems operational</div>
          <Link href="/dashboard"><Settings2 size={15}/> Workspace settings</Link>
          <button onClick={() => { localStorage.removeItem("rivu_access_token"); localStorage.removeItem("rivu_refresh_token"); router.push("/login"); }}><LogOut size={15}/> Sign out</button>
        </div>
      </aside>

      <section className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.breadcrumb}><span>Workspace</span><span>/</span><b>Data Studio</b></div>
          <div className={styles.topActions}><label className={styles.search}><Search size={15}/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search projects…"/><kbd>⌘ K</kbd></label><button className={styles.avatar} title="Account">R</button></div>
        </header>

        <div className={styles.content}>
          <div className={styles.pageHeading}><div><div className={styles.eyebrow}><span/> DATA REFINERY <span className={styles.dot}>/</span> TRANSFORMATION</div><h1>Data Studio <span>↗</span></h1><p>Turn raw data into trusted data. Review every change before it runs.</p></div><div className={styles.headingMeta}><span><ShieldCheck size={14}/> Source version protected</span><span><LockKeyhole size={14}/> Private workspace</span></div></div>

          {!signedIn ? <section className={styles.signin}><LockKeyhole size={25}/><h2>Sign in to your workspace</h2><p>Upload, analyze and refine datasets in your authenticated Rivu workspace.</p><button className={styles.primary} onClick={() => router.push("/login")}>Sign in <ArrowRight size={15}/></button></section> : <>
            {error && <div className={styles.error}><XCircle size={16}/>{error}</div>}
            {notice && <div className={styles.notice}><CheckCircle2 size={16}/>{notice}</div>}
            <section className={styles.stats}>
              <div><span>PROJECTS</span><b>{projects.length}</b><small>Available workspaces</small></div>
              <div><span>ROWS PROFILED</span><b>{profileStats ? Number(profileStats.row_count || 0).toLocaleString() : "—"}</b><small>Current dataset</small></div>
              <div><span>COLUMNS</span><b>{profileStats?.column_count ?? "—"}</b><small>Detected schema</small></div>
              <div><span>NULL CELLS</span><b>{profileStats ? Number(profileStats.total_null_pct || 0).toFixed(1) + "%" : "—"}</b><small>Completeness signal</small></div>
            </section>

            <section className={styles.panel}>
              <div className={styles.panelHeader}><div><div className={styles.sectionEyebrow}>01 / SOURCE</div><h2>Bring in your data</h2><p>Choose a project and upload a source file to begin profiling.</p></div><span className={styles.secure}><LockKeyhole size={13}/> Encrypted in transit</span></div>
              <div className={styles.uploadGrid}>
                <label className={styles.field}><span>DESTINATION PROJECT</span><div className={styles.selectWrap}><Database size={15}/><select value={projectId} onChange={e => setProjectId(e.target.value)} disabled={busy || !projects.length}><option value="">Select a project</option>{filteredProjects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select><ChevronDown size={14}/></div><small>{projects.length ? projects.length + " project(s) available" : "No projects found — create one in Overview."}</small></label>
                <label className={styles.filePicker}><input type="file" accept=".csv,.json,.xlsx,.xls,.parquet" onChange={chooseFile} disabled={busy}/><span className={styles.uploadIcon}><FileUp size={20}/></span><span className={styles.fileCopy}><b>{file ? file.name : "Choose a source file"}</b><small>{file ? (file.size / 1048576).toFixed(2) + " MB · ready to upload" : "CSV, JSON, XLSX, XLS or Parquet · up to 500 MB"}</small></span><span className={styles.browse}>Browse files</span></label>
              </div>
              <div className={styles.actionRow}><button className={styles.primary} onClick={uploadAndProfile} disabled={!file || !projectId || busy}><FileUp size={15}/>{busy && stage.startsWith("Uploading") ? "Uploading…" : "Upload & profile"}</button><span className={styles.hint}>Your original file is preserved.</span>{busy && <span className={styles.busy}><LoaderCircle size={14}/>{stage}</span>}</div>
            </section>

            <section className={styles.pipeline}>
              <div className={styles.pipelineHeading}><div><div className={styles.sectionEyebrow}>02 / REFINE</div><h2>Refinement pipeline</h2><p>AI suggests. You inspect. Rivu executes only after approval.</p></div><span className={styles.stepPill}>{preview ? "Preview ready" : plan ? "Plan generated" : profile ? "Profile ready" : "Waiting for source"}</span></div>
              <div className={styles.pipelineSteps}>
                {[["01","Upload","Bring in source data",true],["02","Profile","Understand quality",!!profile],["03","AI plan","Propose operations",!!plan],["04","Preview","Inspect before / after",!!preview]].map(([n,title,desc,done]) => <div key={String(n)} className={done ? styles.stepDone : styles.step}><span>{done ? <CheckCircle2 size={15}/> : n}</span><b>{title}</b><small>{desc}</small></div>)}
              </div>
              <div className={styles.pipelineActions}><button className={styles.secondary} onClick={generatePlan} disabled={!datasetId || !profile || busy}><Sparkles size={15}/>{busy && stage.includes("AI") ? "Planning…" : "Generate AI plan"}</button><button className={styles.secondary} onClick={previewPlan} disabled={!plan?.id || busy}><WandSparkles size={15}/>{busy && stage.includes("preview") ? "Preparing…" : "Preview changes"}</button><button className={styles.execute} onClick={executePlan} disabled={!plan?.id || !preview || busy}><CheckCircle2 size={15}/>Approve & execute</button></div>
            </section>

            {plan && <section className={styles.panel}><div className={styles.panelHeader}><div><div className={styles.sectionEyebrow}>AI PROPOSAL · REVIEW BEFORE APPLYING</div><h2>{plan.summary || plan.dataset_summary || "Transformation plan"}</h2><p>{plan.detected_domain ? "Detected domain: " + plan.detected_domain + " · " : ""}{plan.operations?.length || 0} proposed operations</p></div><span className={styles.planCount}>{plan.operations?.length || 0} ops</span></div>{!plan.operations?.length ? <p className={styles.empty}>No transformations were recommended for this dataset.</p> : <div className={styles.operationList}>{plan.operations.map((op,i) => <div key={i} className={styles.operation}><span>{String(i+1).padStart(2,"0")}</span><div><b>{op.type.replaceAll("_"," ")}</b><small>{op.column ? "Column: " + op.column : "Row-level operation"}{op.reason ? " · " + op.reason : ""}</small></div><span className={styles.confidence}>{Math.round((op.confidence ?? 0) * 100)}% confidence</span></div>)}</div>}{preview && <div className={styles.preview}><div className={styles.sectionEyebrow}>TRANSFORMATION PREVIEW</div><pre>{JSON.stringify(preview.previews || preview, null, 2)}</pre></div>}</section>}

            {artifacts && <section className={styles.panel}><div className={styles.panelHeader}><div><div className={styles.sectionEyebrow}>03 / OUTPUTS READY</div><h2>Refined dataset artifacts</h2><p>Download the new version or schema. The source version remains unchanged.</p></div></div><div className={styles.artifacts}>{Object.entries(artifacts).map(([format,item]) => item?.download_url && <a key={format} href={item.download_url} target="_blank" rel="noopener noreferrer"><span>{format === "xlsx" ? <FileSpreadsheet size={16}/> : format === "json" || format === "schema.json" ? <FileJson size={16}/> : <Download size={16}/>}</span><b>{item.filename || format}</b><Download size={14}/></a>)}</div></section>}
          </>}
          <footer className={styles.footer}><span>Rivu by WaterTing</span><span><ShieldCheck size={13}/> Source versions are immutable</span><Link href="/dashboard"><ArrowLeft size={13}/> Back to overview</Link></footer>
        </div>
      </section>
    </main>
  );
}
