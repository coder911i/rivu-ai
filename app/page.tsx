"use client";

import { useEffect, useState } from "react";
import { ArrowRight, ChevronDown, Database, FileCheck2, Layers3, Menu, ShieldCheck, Sparkles, Workflow, X, Zap } from "lucide-react";
import { useRouter } from "next/navigation";

const services = [
  { icon: Database, title: "Data Ingestion", text: "Bring CSVs, JSON, spreadsheets and operational exports into one controlled workflow." },
  { icon: Sparkles, title: "AI Understanding", text: "Profile schemas, types, anomalies and relationships before transformations begin." },
  { icon: Workflow, title: "Smart Refinement", text: "Clean, deduplicate, normalize and transform inconsistent data automatically." },
  { icon: FileCheck2, title: "Quality Control", text: "Validate outputs with rules, lineage and visible transformation context." },
];

const stages = ["INGEST", "UNDERSTAND", "CLEAN", "NORMALIZE", "VALIDATE", "READY"];

function Logo() {
  return <a href="#top" className="ts-logo" aria-label="Rivu home"><span className="ts-mark"><i/><i/><i/><i/></span><span>rivu<span className="logo-ai">ai</span></span></a>;
}

function DataShape({ className = "" }: { className?: string }) {
  return <div className={`data-shape ${className}`}><div className="shape-face front"/><div className="shape-face top"/><div className="shape-face side"/></div>;
}

export default function Home() {
  const router = useRouter();
  const [menu, setMenu] = useState(false);
  const [active, setActive] = useState(0);
  const [typed, setTyped] = useState("");

  useEffect(() => {
    const text = "From messy data to intelligence";
    let i = 0;
    const timer = setInterval(() => {
      i += 1;
      setTyped(text.slice(0, i));
      if (i >= text.length) clearInterval(timer);
    }, 55);
    return () => clearInterval(timer);
  }, []);

  const go = (id: string) => {
    setMenu(false);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <main id="top" className="ts-page">
      <div className="dot-pattern" />
      <nav className="ts-nav">
        <div className="nav-inner">
          <Logo />
          <div className={`nav-links ${menu ? "mobile-open" : ""}`}>
            <button onClick={() => go("solutions")}>Solutions</button>
            <button onClick={() => go("engine")}>Data Engine</button>
            <button onClick={() => go("quality")}>Quality</button>
            <button onClick={() => go("about")}>About Rivu</button>
          </div>
          <div className="nav-actions">
            <button className="nav-quote" onClick={() => router.push("/login")}>Get Started <span>→</span></button>
            <button className="mobile-menu" onClick={() => setMenu(!menu)} aria-label="Menu">{menu ? <X/> : <Menu/>}</button>
          </div>
        </div>
      </nav>

      <section className="ts-hero">
        <div className="hero-copy">
          <div className="eyebrow"><span/> AI-NATIVE DATA REFINERY</div>
          <h1>{typed}<span className="cursor"/></h1>
          <p>Rivu is the intelligent layer between raw information and the systems that depend on it.</p>
          <div className="hero-button-row">
            <button className="dark-button" onClick={() => go("solutions")}>Explore Rivu <span>→</span></button>
          </div>
          <div className="hero-points">
            <div><b>•</b> Clean inconsistent operational data</div>
            <div><b>•</b> Understand structure before transforming</div>
            <div><b>•</b> Deliver trusted, analytics-ready outputs</div>
          </div>
        </div>

        <div className="hero-visual">
          <div className="visual-glow"/>
          <div className="visual-grid"/>
          <div className="visual-caption"><b>RIVU ENGINE</b><span>RAW → REFINED → READY</span></div>
          <DataShape className="shape-one"/>
          <DataShape className="shape-two"/>
          <DataShape className="shape-three"/>
          <div className="floating-card raw"><small>RAW INPUT</small><strong>messy_data.csv</strong><span>14,238 rows</span></div>
          <div className="floating-card refined"><small>RIVU REFINING</small><strong>schema detected</strong><span>duplicates resolved</span><span>types normalized</span></div>
          <div className="orb-main"><span/><i/><b/></div>
          <div className="ring ring-1"/><div className="ring ring-2"/><div className="ring ring-3"/>
          <div className="big-rivu">RIVU</div>
        </div>
        <button className="scroll-cue" onClick={() => go("solutions")}>SCROLL TO EXPLORE <span>↓</span></button>
      </section>

      <section className="strip">
        <span>CSV</span><span>JSON</span><span>XLSX</span><span>DATABASE EXPORTS</span><span>API DATA</span><span>AI / ANALYTICS READY</span>
      </section>

      <section id="solutions" className="section intro-section">
        <div className="section-label">01 — THE REFINERY</div>
        <div className="section-heading"><h2>The messy middle<br/><em>is where we work.</em></h2><p>Data rarely arrives ready for analysis. Rivu creates a controlled path from uncertainty to usable intelligence.</p></div>
        <div className="service-grid">
          {services.map(({ icon: Icon, title, text }, i) => <article className="service-card" key={title}><div className="service-top"><span>0{i + 1}</span><Icon/></div><h3>{title}</h3><p>{text}</p><span className="card-arrow">↗</span></article>)}
        </div>
      </section>

      <section id="engine" className="engine-section">
        <div className="engine-heading"><div><div className="section-label light">02 — THE RIVU ENGINE</div><h2>One flow.<br/><em>Every layer.</em></h2></div><p>Move through the refinery stage by stage. The interface stays simple while the data work underneath stays rigorous.</p></div>
        <div className="stage-tabs">{stages.map((s, i) => <button key={s} className={active === i ? "active" : ""} onClick={() => setActive(i)}><span>0{i + 1}</span><b>{s}</b><ArrowRight/></button>)}</div>
        <div className="engine-art">
          <div className="engine-word">REFINE</div><div className="engine-orbit e1"/><div className="engine-orbit e2"/><div className="engine-orbit e3"/>
          <div className="engine-core"><DataShape/><div className="core-dot"/></div>
          <div className="stage-panel"><small>ACTIVE STAGE</small><strong>{stages[active]}</strong><span>{active === 0 ? "CSV / JSON / XLSX" : active === 1 ? "SCHEMA / TYPES / CONTEXT" : active === 2 ? "NULLS / DUPLICATES / ERRORS" : active === 3 ? "FORMATS / NAMES / TYPES" : active === 4 ? "RULES / QUALITY / LINEAGE" : "ANALYTICS / AI / DECISIONS"}</span><div className="panel-bars"><i/><i/><i/><i/></div></div>
        </div>
        <div className="engine-foot"><span>RAW</span><i/><span>UNDERSTAND</span><i/><span>TRANSFORM</span><i/><span>TRUST</span></div>
      </section>

      <section id="quality" className="section quality-section">
        <div className="quality-copy"><div className="section-label">03 — QUALITY INTELLIGENCE</div><h2>Know what changed.<br/><em>Know why.</em></h2><p>Rivu treats data quality as part of the product experience — not a report you discover after the damage is done.</p><div className="quality-list"><span><b>01</b> Traceable transformations</span><span><b>02</b> Validation before delivery</span><span><b>03</b> Source-aware outputs</span></div></div>
        <div className="quality-art"><div className="quality-mesh"/><div className="quality-disc"><small>RIVU</small><b>QUALITY<br/>INTELLIGENCE</b></div><i className="q-orbit q1"/><i className="q-orbit q2"/><i className="q-orbit q3"/></div>
      </section>

      <section id="about" className="about-section">
        <div className="about-art"><div className="about-shape"/><div className="about-logo">RIVU<small>DATA REFINERY</small></div><span>04 / THE MESSY MIDDLE</span></div>
        <div className="about-copy"><div className="section-label">BUILT BY WATERTING</div><h2>Data is not a file.<br/><em>It is a system.</em></h2><p>Sources change. Formats drift. Teams add context. Systems disagree. Rivu gives that movement a consistent refinement layer.</p><button className="dark-button" onClick={() => router.push("/login")}>Enter Rivu <span>→</span></button></div>
      </section>

      <section className="final-cta">
        <div className="cta-grid"/><div className="cta-orb"/><div className="section-label light">RIVU BY WATERTING</div><h2>Your data.<br/><em>Finally ready.</em></h2><p>Turn the messy middle into a reliable intelligence layer.</p><button className="light-button" onClick={() => router.push("/login")}>Enter Rivu <ArrowRight/></button><div className="cta-word">RIVU</div>
      </section>

      <footer className="ts-footer"><Logo/><span>AI-native data refinery</span><span>© 2026 WaterTing</span><button onClick={() => go("top")}>BACK TO TOP ↑</button></footer>
    </main>
  );
}
