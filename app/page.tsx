"use client";

import { useState } from "react";
import { ArrowDownRight, ArrowUpRight, Check, ChevronDown, ChevronRight, Database, FileCheck2, Layers3, Menu, Play, Sparkles, X, Zap } from "lucide-react";

const video = "https://s3-us-west-2.amazonaws.com/coverr/mp4/Busy.mp4";

const capabilities = [
  { n: "01", title: "Ingest anything", text: "CSV, JSON, spreadsheets, exports and inconsistent operational data enter one controlled flow.", icon: Database },
  { n: "02", title: "Understand the shape", text: "Schema discovery and semantic profiling reveal what your data actually contains.", icon: Sparkles },
  { n: "03", title: "Clean with context", text: "Duplicates, nulls, malformed values and anomalies are surfaced before they become decisions.", icon: Layers3 },
  { n: "04", title: "Verified outcomes", text: "Rules, validation gates and traceable transformations create a dependable data layer.", icon: FileCheck2 },
];

const stages = [
  ["Raw", "Unstructured inputs", "CSV · JSON · XLSX"],
  ["Understand", "Semantic profiling", "Schema · Types · Context"],
  ["Clean", "Repair the noise", "Nulls · Duplicates · Errors"],
  ["Normalize", "One consistent model", "Formats · Names · Types"],
  ["Validate", "Quality gates", "Rules · Confidence · Checks"],
  ["Intelligence", "Ready to use", "Analytics · AI · Decisions"],
];

const faqs = [
  ["What kind of data can Rivu process?", "Rivu is designed around messy operational data: spreadsheets, CSVs, JSON, exports and inconsistent datasets that need to become structured and analytics-ready."],
  ["How does Rivu keep transformations explainable?", "Every transformation can be represented as a visible step with before/after context, validation and a traceable reason for the change."],
  ["Does Rivu replace our existing data stack?", "Rivu is positioned as the refinement layer between raw sources and the systems where teams analyze, model or operationalize data."],
  ["What happens to the original data?", "The product experience is designed around preserving the source while producing a cleaned, normalized output that can be reviewed and trusted."],
];

function Logo() {
  return <a className="brand" href="#top" aria-label="Rivu AI">
    <span className="brand-mark"><i/><i/><i/><i/></span><span className="brand-word">Rivu<span>ai</span></span>
  </a>;
}

function DotField() {
  return <div className="dot-field" aria-hidden="true">{Array.from({ length: 96 }).map((_, i) => <i key={i} />)}</div>;
}

function DataOrb({ small = false }: { small?: boolean }) {
  return <div className={small ? "data-orb small" : "data-orb"}><span/><b/><i/><em/></div>;
}

function Cube() {
  return <div className="cube3d"><i/><i/><i/><i/><i/><i/><b>R</b></div>;
}

export default function Home() {
  const [menu, setMenu] = useState(false);
  const [stage, setStage] = useState(0);
  const [motion, setMotion] = useState(true);
  const [openFaq, setOpenFaq] = useState(0);
  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

  return <main id="top" className={motion ? "site motion" : "site paused"}>
    <div className="noise" />

    <nav className="topbar">
      <Logo />
      <div className={menu ? "navlinks open" : "navlinks"}>
        {[["01", "Capabilities", "capabilities"], ["02", "Refinery", "refinery"], ["03", "Quality", "quality"], ["04", "FAQ", "faq"]].map(([n, label, id]) => <button key={id} onClick={() => { setMenu(false); jump(id); }}><small>{n}</small>{label}</button>)}
      </div>
      <div className="top-actions">
        <button className="motion-toggle" onClick={() => setMotion(!motion)}>{motion ? "PAUSE" : "PLAY"}</button>
        <button className="dark-pill" onClick={() => window.location.href="/login"}>ENTER RIVU <ArrowUpRight size={13}/></button>
        <button className="menu-btn" onClick={() => setMenu(!menu)}>{menu ? <X size={18}/> : <Menu size={18}/>}</button>
      </div>
    </nav>

    <section className="hero-v" id="product">
      <div className="hero-copy">
        <div className="tiny-label"><b/> AI-NATIVE DATA REFINERY</div>
        <h1>From raw data<br/><span>to ready.</span></h1>
        <p>Rivu turns the messy middle of your data stack into a clean, verified and intelligence-ready foundation.</p>
        <button className="light-pill" onClick={() => jump("refinery")}>Explore the refinery <ArrowDownRight size={15}/></button>
      </div>
      <div className="hero-scene">
        <div className="scene-copy"><strong>Rivu Engine</strong><span>refining intelligence at every layer</span></div>
        <div className="pink-route"><i/><i/><i/></div>
        <div className="blue-route"><i/><i/></div>
        <DotField />
        <div className="scene-floor" />
        <div className="scene-cluster c1"><span/><span/><span/><span/><b>RAW</b></div>
        <div className="scene-cluster c2"><span/><span/><span/><span/><b>DATA</b></div>
        <div className="scene-cluster c3"><span/><span/><span/><span/><b>AI</b></div>
        <DataOrb />
        <DataOrb small />
        <div className="hero-node"><div className="node-core">R</div><span>activation, simplified</span><small>schema detected</small><small>issues resolved</small><small>quality passed</small></div>
        <div className="hero-cube"><Cube/></div>
      </div>
      <div className="scroll-mark"><span>SCROLL TO EXPLORE</span><b/></div>
    </section>

    <section className="statement" id="capabilities">
      <div className="statement-head"><div><div className="tiny-label dark"><b/> THE REFINERY</div><h2>Designed for today&apos;s data,<br/><span>beyond legacy workflows.</span></h2></div><p>Rivu is the intelligence layer between chaotic sources and the systems your team depends on.</p></div>
      <div className="cap-grid">{capabilities.map(({ n, title, text, icon: Icon }) => <article className="cap" key={n}><div className="cap-icon"><Icon size={22}/></div><small>{n}</small><h3>{title}</h3><p>{text}</p><ArrowUpRight className="cap-arrow" size={17}/></article>)}</div>
    </section>

    <section className="dark-chapter" id="refinery">
      <div className="chapter-intro"><div className="tiny-label"><b/> THE RIVU ENGINE</div><h2>Clean information.<br/><span>Clear decisions.</span></h2><button className="outline-pill" onClick={() => jump("quality")}>See how it works <ChevronRight size={14}/></button></div>
      <div className="chapter-tabs">{stages.slice(0, 3).map((s, i) => <button key={s[0]} onClick={() => setStage(i)} className={stage === i ? "active" : ""}><span>{s[0]}</span><ArrowUpRight size={14}/></button>)}<button onClick={() => setStage(3)} className={stage === 3 ? "active" : ""}><span>Apply</span><ArrowUpRight size={14}/></button></div>
      <div className="engine-word">RIVU</div>
      <div className="engine-scene">
        <div className="engine-ring r1"/><div className="engine-ring r2"/><div className="engine-ring r3"/>
        <Cube/><DataOrb small/>
        <div className="engine-data"><span>01</span><b>{stages[stage][0]}</b><small>{stages[stage][1]}</small><em>{stages[stage][2]}</em></div>
      </div>
      <div className="chapter-foot"><span>01 — UNDERSTAND</span><span>02 — TRANSFORM</span><span>03 — TRUST</span></div>
    </section>

    <section className="split-story" id="quality">
      <div className="story-copy"><div className="tiny-label dark"><b/> QUALITY INTELLIGENCE</div><h2>Know what changed.<br/><span>Know why.</span></h2><p>Rivu makes the transformation visible. Every correction has context, every rule has a reason, and every output can be traced back to its source.</p><div className="story-stats"><div><b>98.7</b><small>QUALITY SCORE</small></div><div><b>0</b><small>DATA LOSS</small></div><div><b>100%</b><small>TRACEABLE</small></div></div></div>
      <div className="quality-scene"><div className="quality-grid"/><div className="quality-disc"><span>98.7</span><small>HEALTH</small></div>{[1,2,3].map(i => <i key={i} className={`q-orbit q${i}`}/>)}</div>
    </section>

    <section className="industrial" id="about">
      <div className="industrial-media"><video src={video} autoPlay muted loop playsInline/><div className="media-overlay"/><span>RIVU / 04</span></div>
      <div className="industrial-copy"><div className="tiny-label dark"><b/> BUILT FOR THE MESSY MIDDLE</div><h2>Data is not a file.<br/><span>It is a system.</span></h2><p>When data moves through people, products and platforms, consistency becomes the difference between information and intelligence.</p><button className="light-pill" onClick={() => jump("faq")}>Read the principles <ArrowDownRight size={15}/></button></div>
    </section>

    <section className="faq" id="faq">
      <div className="faq-head"><div className="tiny-label dark"><b/> QUESTIONS, WITHOUT THE NOISE</div><h2>How Rivu works<br/><span>in the real world.</span></h2></div>
      <div className="faq-list">{faqs.map(([q, a], i) => <div className={openFaq === i ? "faq-row open" : "faq-row"} key={q}><button onClick={() => setOpenFaq(openFaq === i ? -1 : i)}><span><small>0{i + 1}</small>{q}</span><ChevronDown size={18}/></button><div className="faq-answer"><p>{a}</p></div></div>)}</div>
    </section>

    <section className="dark-close" id="product-end">
      <div className="close-glow"/><div className="close-grid"/><div className="close-kicker">RIVU BY WATERTING</div><h2>Your data.<br/><span>Finally ready.</span></h2><p>Build a reliable intelligence layer from the information you already have.</p><button className="light-pill" onClick={() => jump("product")}>Enter Rivu <ArrowUpRight size={15}/></button><div className="close-word">RIVU</div>
    </section>

    <footer><Logo/><span>AI-native data refinery</span><span>© 2026 WaterTing</span><button onClick={() => jump("top")}>BACK TO TOP ↑</button></footer>
  </main>;
}