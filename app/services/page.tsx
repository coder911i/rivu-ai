"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft, ArrowRight, CheckCircle2, ChevronDown, Database, Download,
  FileJson, FileSpreadsheet, FileUp, LoaderCircle, LockKeyhole, RefreshCw,
  ShieldCheck, Sparkles, WandSparkles, XCircle
} from "lucide-react";
import { authFetch } from "../../lib/api";
import BrandLogo from "../../lib/BrandLogo";
import CursorField from "../../lib/CursorField";
import styles from "./services.module.css";

type Project = { id: string; name: string; dataset_count?: number };
type PlanOperation = { type: string; column?: string | null; confidence?: number; reason?: string; parameters?: Record<string, unknown> };
type Plan = { id: string; summary?: string; dataset_summary?: string; detected_domain?: string; estimated_quality_gain?: number; operations: PlanOperation[]; status?: string };
type Artifact = { filename: string; download_url: string; size_bytes?: number };
type ArtifactMap = Record<string, Artifact>;
type DatasetProfile = { dataset?: { id: string; name: string; status: string }; profile?: { row_count: number; column_count: number; duplicate_row_count: number; total_null_pct: number }; version?: { number: number; quality_score?: number | null } };
type ApiError = { detail?: string | { message?: string }; message?: string };

const MAX_BYTES = 500 * 1024 * 1024;
const ACCEPTED = new Set(["csv", "json", "xlsx", "xls", "parquet"]);

function messageFrom(data: ApiError, fallback: string) {
  if (typeof data?.detail === "string") return data.detail;
  if (data?.detail && typeof data.detail === "object" && typeof data.detail.message === "string") return data.detail.message;
  return data?.message || fallback;
}
async function jsonOrEmpty(response: Response) {
  return await response.json().catch(() => ({})) as Record<string, any>;
}

export default function ServicesPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [datasetId, setDatasetId] = useState("");
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [preview, setPreview] = useState<Record<string, any> | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactMap | null>(null);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState<"idle" | "upload" | "profile" | "plan" | "preview" | "execute" | "done">("idle");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    setAuthReady(true);
    const token = localStorage.getItem("rivu_access_token");
    if (!token) {
      setNotice("Sign in to use Data Transformation Services. Your files remain in your private workspace.");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const response = await authFetch("/projects/");
        if (response.status === 401) { router.push("/login"); return; }
        const data = await jsonOrEmpty(response);
        if (!response.ok) throw new Error(messageFrom(data, "Could not load projects."));
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

  const stageLabel = useMemo(() => ({
    idle: "Ready for your source data",
    upload: "Uploading source data",
    profile: "Profiling structure and quality",
    plan: "Building an AI refinement plan",
    preview: "Preparing transformation preview",
    execute: "Applying approved transformations",
    done: "Refinement complete",
  }[stage]), [stage]);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] || null;
    setError("");
    setNotice("");
    setPlan(null); setPreview(null); setArtifacts(null); setProfile(null); setDatasetId("");
    if (!selected) { setFile(null); return; }
    const ext = selected.name.split(".").pop()?.toLowerCase() || "";
    if (!ACCEPTED.has(ext)) {
      setFile(null);
      setError("Unsupported file type. Use CSV, JSON, XLSX, XLS or Parquet. PDF catalogues are not supported by this transformation pipeline yet.");
      event.target.value = "";
      return;
    }
    if (selected.size > MAX_BYTES) {
      setFile(null); setError("File exceeds the 500 MB client limit. Choose a smaller file."); event.target.value = ""; return;
    }
    if (selected.size === 0) {
      setFile(null); setError("This file is empty."); event.target.value = ""; return;
    }
    setFile(selected);
  }

  async function uploadAndProfile() {
    if (!file || !projectId || busy) return;
    setBusy(true); setError(""); setNotice(""); setStage("upload");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("name", file.name.replace(/\.[^.]+$/, "").slice(0, 300));
      const uploadResponse = await authFetch("/datasets/projects/" + encodeURIComponent(projectId) + "/upload", { method: "POST", body: form });
      const uploaded = await jsonOrEmpty(uploadResponse);
      if (!uploadResponse.ok) throw new Error(messageFrom(uploaded as ApiError, "Upload failed."));
      const id = String(uploaded.dataset?.id || "");
      if (!id) throw new Error("Upload completed but the API did not return a dataset ID.");
      setDatasetId(id);
      setStage("profile");
      setNotice("Upload secured. Waiting for the profiling worker to finish…");

      let ready: DatasetProfile | null = null;
      for (let attempt = 0; attempt < 30; attempt++) {
        await new Promise(resolve => window.setTimeout(resolve, 1800));
        const [pResponse, qResponse] = await Promise.all([
          authFetch("/datasets/" + id + "/profile"),
          authFetch("/datasets/" + id + "/quality"),
        ]);
        if (pResponse.status === 401 || qResponse.status === 401) { router.push("/login"); return; }
        if (pResponse.ok && qResponse.ok) {
          ready = await jsonOrEmpty(pResponse) as DatasetProfile;
          await qResponse.json().catch(() => ({}));
          break;
        }
        if (![202, 404].includes(pResponse.status) && !pResponse.ok) {
          const data = await jsonOrEmpty(pResponse);
          throw new Error(messageFrom(data as ApiError, "Profiling failed."));
        }
      }
      if (!ready) throw new Error("Profiling is taking longer than expected. Your upload is saved; retry analysis in the dataset workspace.");
      setProfile(ready);
      setNotice("Profile ready. Generate a proposed plan to inspect the changes before applying them.");
      setStage("idle");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not upload and profile this file.");
      setStage("idle");
    } finally { setBusy(false); }
  }

  async function generatePlan() {
    if (!datasetId || busy) return;
    setBusy(true); setError(""); setStage("plan"); setNotice("");
    try {
      const response = await authFetch("/datasets/" + datasetId + "/ai-plan", { method: "POST" });
      const data = await jsonOrEmpty(response);
      if (!response.ok) throw new Error(messageFrom(data as ApiError, "AI plan generation failed."));
      setPlan(data as Plan); setPreview(null); setArtifacts(null);
      setNotice("Plan generated. Review every proposed operation before execution.");
      setStage("idle");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not generate a transformation plan.");
      setStage("idle");
    } finally { setBusy(false); }
  }

  async function previewPlan() {
    if (!datasetId || !plan?.id || busy) return;
    setBusy(true); setError(""); setStage("preview");
    try {
      const response = await authFetch("/datasets/" + datasetId + "/transform/preview", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plan_id: plan.id })
      });
      const data = await jsonOrEmpty(response);
      if (!response.ok) throw new Error(messageFrom(data as ApiError, "Preview failed."));
      setPreview(data); setNotice("Preview ready. The original dataset will remain unchanged.");
      setStage("idle");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create preview.");
      setStage("idle");
    } finally { setBusy(false); }
  }

  async function executePlan() {
    if (!datasetId || !plan?.id || busy) return;
    if (!window.confirm("Apply this plan and create a new immutable dataset version? The source version will not be overwritten.")) return;
    setBusy(true); setError(""); setStage("execute");
    try {
      const headers = { "Content-Type": "application/json" };
      const body = JSON.stringify({ plan_id: plan.id });
      const approval = await authFetch("/datasets/" + datasetId + "/transform/approve", { method: "POST", headers, body });
      const approved = await jsonOrEmpty(approval);
      if (!approval.ok) throw new Error(messageFrom(approved as ApiError, "Plan approval failed."));
      const response = await authFetch("/datasets/" + datasetId + "/transform/execute", { method: "POST", headers, body });
      const data = await jsonOrEmpty(response);
      if (!response.ok) throw new Error(messageFrom(data as ApiError, "Transformation failed."));
      setArtifacts((data.artifacts || null) as ArtifactMap | null);
      setNotice("Transformation complete. A new version was created; the original source remains preserved.");
      setStage("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Transformation failed.");
      setStage("idle");
    } finally { setBusy(false); }
  }

  return (
    <main className={styles.page}>
      <CursorField />
      <header className={styles.nav}>
        <BrandLogo href="/" className={styles.logo} />
        <nav><a href="/#solutions">Solutions</a><a className={styles.activeLink} href="/services">Our Services</a><a href="/dashboard">Workspace</a></nav>
        <button className={styles.back} onClick={() => router.push("/dashboard")}><ArrowLeft size={15}/> Workspace</button>
      </header>

      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <div className={styles.eyebrow}><span/> RIVU DATA REFINERY / SERVICES</div>
          <h1>Data transformation,<br/><em>without the guesswork.</em></h1>
          <p>Profile messy datasets, get an AI-proposed refinement plan, inspect a preview, and approve changes before Rivu writes a new version.</p>
          <div className={styles.trust}><span><ShieldCheck size={15}/> Private workspace</span><span><LockKeyhole size={15}/> Authenticated API</span><span><CheckCircle2 size={15}/> Source version preserved</span></div>
        </div>
        <div className={styles.visual} aria-hidden="true">
          <div className={styles.visualGrid}/><div className={styles.visualOrb}/><div className={styles.visualCore}><Database size={28}/><b>RIVU</b><small>TRANSFORM ENGINE</small></div>
          <div className={styles.floatCard + " " + styles.cardRaw}><small>INPUT</small><b>messy_data.csv</b><span>Profile · Validate</span></div>
          <div className={styles.floatCard + " " + styles.cardClean}><small>OUTPUT</small><b>refined_v2</b><span>New immutable version</span></div>
        </div>
      </section>

      <section className={styles.serviceIntro}>
        <div><div className={styles.kicker}>01 / DATA TRANSFORMATION SERVICES</div><h2>From raw files to<br/><em>trusted data.</em></h2></div>
        <p>Rivu uses its existing profiling, quality, AI planning and deterministic transformation APIs. AI proposes operations; you review and approve before execution.</p>
      </section>

      <section className={styles.steps}>
        {[
          {n:"01",title:"Upload",text:"Bring CSV, JSON, XLSX, XLS or Parquet into a project."},
          {n:"02",title:"Understand",text:"Profile columns, nulls, duplicates and quality."},
          {n:"03",title:"Preview",text:"Review the proposed operations and before/after samples."},
          {n:"04",title:"Refine",text:"Approve the plan and export a new dataset version."},
        ].map(item => <article key={item.n}><span>{item.n}</span><h3>{item.title}</h3><p>{item.text}</p></article>)}
      </section>

      <section className={styles.workbench} id="start">
        <div className={styles.workbenchHead}><div><div className={styles.kicker}>02 / START A TRANSFORMATION</div><h2>Your data workbench</h2><p>Files are sent to your authenticated Rivu API and stored under your selected project.</p></div><span className={styles.securePill}><LockKeyhole size={13}/> Authenticated</span></div>
        {!authReady ? <div className={styles.state}><LoaderCircle className={styles.spin}/> Loading service…</div> : !localStorage.getItem("rivu_access_token") ? (
          <div className={styles.signin}><LockKeyhole size={22}/><h3>Sign in to transform data</h3><p>Use your Rivu workspace to upload, analyze and refine datasets securely.</p><button className={styles.primary} onClick={() => router.push("/login")}>Sign in <ArrowRight size={15}/></button></div>
        ) : (
          <>
            <div className={styles.controls}>
              <label className={styles.field}><span>WORKSPACE PROJECT</span><div className={styles.selectWrap}><Database size={16}/><select value={projectId} onChange={e => setProjectId(e.target.value)} disabled={busy || projects.length === 0}><option value="">Select a project</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select><ChevronDown size={14}/></div></label>
              <label className={styles.filePicker}><input type="file" accept=".csv,.json,.xlsx,.xls,.parquet" onChange={chooseFile} disabled={busy}/><FileUp size={22}/><b>{file ? file.name : "Choose a dataset file"}</b><span>{file ? (file.size / (1024 * 1024)).toFixed(2) + " MB · ready to upload" : "CSV · JSON · XLSX · XLS · Parquet · Max 500 MB"}</span></label>
            </div>
            <div className={styles.actions}>
              <button className={styles.primary} onClick={uploadAndProfile} disabled={!file || !projectId || busy}><FileUp size={15}/>{busy && stage === "upload" ? "Uploading…" : "Upload & profile"}</button>
              <button className={styles.secondary} onClick={generatePlan} disabled={!datasetId || !profile || busy}><Sparkles size={15}/>{busy && stage === "plan" ? "Planning…" : "Generate AI plan"}</button>
              <button className={styles.secondary} onClick={previewPlan} disabled={!plan?.id || busy}><WandSparkles size={15}/>{busy && stage === "preview" ? "Previewing…" : "Preview changes"}</button>
              <button className={styles.execute} onClick={executePlan} disabled={!plan?.id || !preview || busy}><CheckCircle2 size={15}/>{busy && stage === "execute" ? "Refining…" : "Approve & execute"}</button>
            </div>
            {busy && <div className={styles.progress}><LoaderCircle className={styles.spin}/><span>{stageLabel}</span><div><i/></div></div>}
            {error && <div className={styles.error}><XCircle size={16}/><span>{error}</span></div>}
            {notice && <div className={styles.notice}><CheckCircle2 size={16}/><span>{notice}</span></div>}
            {profile?.profile && <div className={styles.profileGrid}>
              <div><span>ROWS</span><b>{Number(profile.profile.row_count || 0).toLocaleString()}</b></div>
              <div><span>COLUMNS</span><b>{profile.profile.column_count ?? "—"}</b></div>
              <div><span>DUPLICATE ROWS</span><b>{Number(profile.profile.duplicate_row_count || 0).toLocaleString()}</b></div>
              <div><span>NULL CELLS</span><b>{Number(profile.profile.total_null_pct || 0).toFixed(1)}%</b></div>
            </div>}
            {plan && <div className={styles.plan}>
              <div className={styles.planHead}><div><div className={styles.kicker}>AI PROPOSAL · REVIEW BEFORE APPLYING</div><h3>{plan.summary || plan.dataset_summary || "Transformation plan"}</h3><p>{plan.detected_domain ? "Detected domain: " + plan.detected_domain + " · " : ""}{plan.operations?.length || 0} proposed operations</p></div><span className={styles.planCount}>{plan.operations?.length || 0} ops</span></div>
              {!plan.operations?.length ? <p className={styles.empty}>No transformations were recommended for this dataset.</p> : <div className={styles.operationList}>{plan.operations.map((op,i) => <div key={i} className={styles.operation}><span className={styles.opIndex}>{String(i+1).padStart(2,"0")}</span><div><b>{op.type.replaceAll("_"," ")}</b><small>{op.column ? "Column: " + op.column : "Row-level operation"}{op.reason ? " · " + op.reason : ""}</small></div><span className={styles.confidence}>{Math.round((op.confidence ?? 0) * 100)}%</span></div>)}</div>}
              {preview && <div className={styles.preview}><div className={styles.kicker}>PREVIEW RESPONSE</div><pre>{JSON.stringify(preview.previews || preview, null, 2)}</pre></div>}
            </div>}
            {artifacts && <div className={styles.exports}><div><div className={styles.kicker}>03 / OUTPUTS READY</div><h3>Refined dataset artifacts</h3><p>Download the new version or schema. Links are time-limited by the storage provider.</p></div><div className={styles.exportLinks}>{Object.entries(artifacts).map(([format,item]) => item?.download_url && <a key={format} href={item.download_url} target="_blank" rel="noopener noreferrer"><span>{format === "xlsx" ? <FileSpreadsheet size={16}/> : format === "json" || format === "schema.json" ? <FileJson size={16}/> : <Download size={16}/>}</span><b>{item.filename || format}</b><Download size={14}/></a>)}</div></div>}
          </>
        )}
      </section>

      <section className={styles.securityNote}><ShieldCheck size={18}/><div><b>Built around controlled changes</b><p>Server-side authentication and organization role checks remain authoritative. Uploads are validated by the backend. AI creates a plan only; deterministic allowlisted operations run after explicit approval, and source data is kept as an immutable version.</p></div></section>
      <footer className={styles.footer}><BrandLogo href="/" className={styles.logo}/><span>Rivu by WaterTing · Data Transformation Services</span><a href="/dashboard">Open workspace <ArrowRight size={13}/></a></footer>
    </main>
  );
}
