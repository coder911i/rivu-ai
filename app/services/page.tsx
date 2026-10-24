"use client";

import { useSyncExternalStore, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BrainCircuit,
  Database,
  FileCheck2,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

function getSnapshot() {
  return typeof window !== "undefined" && Boolean(localStorage.getItem("rivu_access_token"));
}

function getServerSnapshot() {
  return false;
}

const transformationServices = [
  {
    step: "01",
    icon: Database,
    title: "Ingestion & Multi-Format Parsing",
    badge: "Streaming Ingestion",
    description:
      "Ingest messy operational files up to 500MB without memory exhaustion. Auto-detects encoding (UTF-8, Latin1, ASCII) and canonical format (CSV, TSV, XLSX, JSON, Parquet).",
    capabilities: [
      "Streamed SHA-256 chunked hashing",
      "Automatic delimiter & encoding detection",
      "Polars zero-copy columnar ingestion",
      "Immutable Raw Version 1 persistence",
    ],
  },
  {
    step: "02",
    icon: BrainCircuit,
    title: "Statistical Profiling & Schema Inference",
    badge: "Deterministic Profiling",
    description:
      "Deeply inspect data shapes before applying transformations. Infer semantic types (dates, emails, phone numbers, UUIDs) and identify null distributions and duplicate rows.",
    capabilities: [
      "Column-level null rate & uniqueness percentages",
      "Statistical metrics (mean, min, max, std-dev)",
      "Automated duplicate record discovery",
      "Heuristic & regex semantic type inference",
    ],
  },
  {
    step: "03",
    icon: Sparkles,
    title: "AI-Native Transformation Planning",
    badge: "Human-in-the-Loop AI",
    description:
      "Our AI plans; deterministic code executes. Rivu generates structured, explainable cleaning and normalization plans with per-operation confidence scores.",
    capabilities: [
      "LLMs never touch or mutate customer data directly",
      "Explainable reasoning for every proposed change",
      "Confidence-weighted operations",
      "Strict schema-validated plan generation",
    ],
  },
  {
    step: "04",
    icon: Workflow,
    title: "Preview, Approval & Deterministic Execution",
    badge: "Quality Gate",
    description:
      "Inspect side-by-side before/after value previews. Require explicit human approval before creating a new immutable dataset version in storage.",
    capabilities: [
      "Before/after 5-row diff preview per operation",
      "Explicit user approval endpoint enforcement",
      "Deterministic Polars execution engine",
      "Version lineage tracking (v1 -> v2 -> v3)",
    ],
  },
  {
    step: "05",
    icon: FileCheck2,
    title: "Automated Quality Reports & Export",
    badge: "Enterprise Ready",
    description:
      "Export certified data-quality audits and reports in downloadable PDF and JSON formats with comprehensive issue severities and recommendations.",
    capabilities: [
      "Downloadable branded ReportLab PDF audits",
      "Machine-readable JSON data-quality export",
      "Dimensional scoring (completeness, validity, integrity)",
      "Workspace and tenant data isolation",
    ],
  },
];

const supportedFormats = [
  { name: "CSV / TSV", ext: ".csv, .tsv", desc: "Comma and tab-separated raw tabular data" },
  { name: "Excel Spreadsheets", ext: ".xlsx, .xls", desc: "Multi-sheet financial and business workbooks" },
  { name: "JSON / JSONL", ext: ".json", desc: "Semi-structured objects and nested array records" },
  { name: "Apache Parquet", ext: ".parquet", desc: "High-performance compressed columnar data" },
];

export default function ServicesPage() {
  const router = useRouter();
  const isAuthenticated = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const [selectedService, setSelectedService] = useState(0);

  return (
    <main className="ts-page" style={{ minHeight: "100vh", background: "#08080d", color: "#f2f2f4" }}>
      <nav className="ts-nav" style={{ borderBottom: "1px solid #1f1f28" }}>
        <div className="nav-inner">
          <Link href="/" className="ts-logo" aria-label="Rivu home">
            <span className="ts-mark"><i /><i /><i /><i /></span>
            <span>rivu<span className="logo-ai">ai</span></span>
          </Link>
          <div className="nav-links">
            <Link href="/" style={{ color: "#a0a0ab", textDecoration: "none", fontSize: "14px" }}>Home</Link>
            <Link href="/services" style={{ color: "#ffffff", fontWeight: 600, textDecoration: "none", fontSize: "14px" }}>Services</Link>
            <Link href="/#engine" style={{ color: "#a0a0ab", textDecoration: "none", fontSize: "14px" }}>Data Engine</Link>
            <Link href="/#quality" style={{ color: "#a0a0ab", textDecoration: "none", fontSize: "14px" }}>Quality</Link>
          </div>
          <div className="nav-actions">
            {isAuthenticated ? (
              <button className="nav-quote" onClick={() => router.push("/dashboard")}>
                Dashboard <span>→</span>
              </button>
            ) : (
              <>
                <Link href="/login" style={{ color: "#c5c5d2", textDecoration: "none", fontSize: "14px", marginRight: "12px" }}>
                  Sign in
                </Link>
                <button className="nav-quote" onClick={() => router.push("/signup")}>
                  Get Started <span>→</span>
                </button>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section style={{ maxWidth: "1200px", margin: "0 auto", padding: "80px 24px 60px" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", background: "rgba(159,140,255,0.1)", border: "1px solid rgba(159,140,255,0.25)", padding: "6px 14px", borderRadius: "100px", fontSize: "11px", letterSpacing: "1.5px", color: "#a28eff", marginBottom: "24px" }}>
          <Sparkles size={13} /> DATA TRANSFORMATION SERVICES
        </div>
        <h1 style={{ fontSize: "clamp(36px, 5vw, 64px)", lineHeight: 1.05, letterSpacing: "-0.04em", margin: "0 0 20px", fontWeight: 700 }}>
          Deterministic Data Refinement.<br />
          <em style={{ fontStyle: "normal", color: "#9f8cff" }}>Governed by AI intelligence.</em>
        </h1>
        <p style={{ maxWidth: "680px", color: "#9898a8", fontSize: "18px", lineHeight: 1.6, margin: "0 0 36px" }}>
          Rivu converts raw, messy, and corrupted enterprise datasets into production-grade intelligence.
          Every transformation is explainable, isolated per organization, and approved by humans before execution.
        </p>
        <div style={{ display: "flex", gap: "14px", flexWrap: "wrap" }}>
          <button
            onClick={() => router.push(isAuthenticated ? "/dashboard" : "/signup")}
            style={{ background: "#f4f3ef", color: "#111", border: 0, padding: "14px 28px", borderRadius: "12px", fontWeight: 700, fontSize: "15px", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: "8px" }}
          >
            Launch Data Refinery <ArrowRight size={17} />
          </button>
          <Link
            href="/#engine"
            style={{ background: "#14141d", color: "#d0d0dc", border: "1px solid #282836", padding: "14px 24px", borderRadius: "12px", fontWeight: 600, fontSize: "15px", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "8px" }}
          >
            Inspect Engine Specs
          </Link>
        </div>
      </section>

      {/* Services Grid */}
      <section style={{ maxWidth: "1200px", margin: "0 auto", padding: "20px 24px 80px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "24px" }}>
          {transformationServices.map((service, index) => {
            const Icon = service.icon;
            const isSelected = selectedService === index;
            return (
              <div
                key={service.step}
                onClick={() => setSelectedService(index)}
                style={{
                  background: isSelected ? "rgba(25, 23, 35, 0.95)" : "rgba(14, 14, 20, 0.8)",
                  border: isSelected ? "1px solid #7c5cff" : "1px solid #1f1f28",
                  borderRadius: "20px",
                  padding: "32px",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  boxShadow: isSelected ? "0 12px 40px rgba(124, 92, 255, 0.15)" : "none",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                  <div style={{ width: "42px", height: "42px", borderRadius: "12px", background: "rgba(159,140,255,0.12)", color: "#a28eff", display: "grid", placeItems: "center" }}>
                    <Icon size={20} />
                  </div>
                  <span style={{ fontSize: "11px", letterSpacing: "1px", color: "#6e6e7d", fontWeight: 600 }}>{service.step} / 05</span>
                </div>
                <div style={{ display: "inline-block", fontSize: "11px", color: "#8d79ff", background: "rgba(141,121,255,0.1)", padding: "3px 8px", borderRadius: "6px", marginBottom: "12px", fontWeight: 600 }}>
                  {service.badge}
                </div>
                <h3 style={{ fontSize: "20px", margin: "0 0 10px", fontWeight: 600, color: "#ffffff" }}>{service.title}</h3>
                <p style={{ fontSize: "14px", color: "#8e8e9c", lineHeight: 1.6, margin: "0 0 20px" }}>{service.description}</p>
                <div style={{ borderTop: "1px solid #20202c", paddingTop: "16px" }}>
                  <ul style={{ margin: 0, paddingLeft: "18px", color: "#b2b2c2", fontSize: "13px", lineHeight: 1.8 }}>
                    {service.capabilities.map((cap, i) => (
                      <li key={i}>{cap}</li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Supported Data Formats */}
      <section style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px 80px" }}>
        <div style={{ border: "1px solid #22222e", borderRadius: "24px", padding: "40px", background: "#0e0e14" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: "20px", marginBottom: "32px" }}>
            <div>
              <div style={{ fontSize: "11px", letterSpacing: "1.5px", color: "#8d80bd", fontWeight: 600 }}>COMPATIBILITY MATRIX</div>
              <h2 style={{ fontSize: "28px", margin: "8px 0 0", fontWeight: 700 }}>Supported Ingestion Formats</h2>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#8fe1b3", fontSize: "13px" }}>
              <ShieldCheck size={16} /> Up to 500MB per dataset upload
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
            {supportedFormats.map((format) => (
              <div key={format.name} style={{ background: "#14141c", border: "1px solid #22222d", borderRadius: "14px", padding: "20px" }}>
                <b style={{ display: "block", fontSize: "16px", color: "#fff", marginBottom: "4px" }}>{format.name}</b>
                <code style={{ fontSize: "12px", color: "#a28eff", background: "rgba(162,142,255,0.1)", padding: "2px 6px", borderRadius: "4px", display: "inline-block", marginBottom: "8px" }}>
                  {format.ext}
                </code>
                <p style={{ margin: 0, fontSize: "12px", color: "#777785", lineHeight: 1.5 }}>{format.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section style={{ borderTop: "1px solid #1a1a24", padding: "60px 24px", textAlign: "center" }}>
        <h2 style={{ fontSize: "32px", margin: "0 0 12px", fontWeight: 700 }}>Ready to transform your datasets?</h2>
        <p style={{ color: "#8a8a98", margin: "0 0 28px", fontSize: "16px" }}>
          Open your secure workspace or sign in to start refining operational data now.
        </p>
        <button
          onClick={() => router.push(isAuthenticated ? "/dashboard" : "/signup")}
          style={{ background: "#7c5cff", color: "#fff", border: 0, padding: "14px 32px", borderRadius: "12px", fontWeight: 700, fontSize: "15px", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: "8px" }}
        >
          {isAuthenticated ? "Enter Workspace" : "Get Started Now"} <ArrowRight size={17} />
        </button>
      </section>

      <footer className="ts-footer" style={{ borderTop: "1px solid #181822" }}>
        <Link href="/" className="ts-logo" aria-label="Rivu home">
          <span className="ts-mark"><i /><i /><i /><i /></span>
          <span>rivu<span className="logo-ai">ai</span></span>
        </Link>
        <span>Data Transformation Services</span>
        <span>© 2026 WaterTing</span>
        <button onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>BACK TO TOP ↑</button>
      </footer>
    </main>
  );
}
