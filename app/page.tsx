"use client";

import { useEffect, useState } from "react";
import { ArrowDownRight, ArrowUpRight, ChevronDown, ChevronRight, Database, FileCheck2, Layers3, Menu, Sparkles, X } from "lucide-react";
import { useRouter } from "next/navigation";

const capabilities = [
  ["01", "Ingest", "Bring files, exports and operational data into one controlled starting point.", Database],
  ["02", "Understand", "Profile structure, types, relationships and anomalies before changing anything.", Sparkles],
  ["03", "Refine", "Clean, deduplicate, normalize and transform the messy middle automatically.", Layers3],
  ["04", "Trust", "Validate every output with rules, lineage and quality checks.", FileCheck2],
] as const;

const stages = [
  ["01", "INGEST", "CSV / JSON / XLSX"],
  ["02", "PROFILE", "SCHEMA / TYPES / CONTEXT"],
  ["03", "CLEAN", "NULLS / DUPLICATES / ERRORS"],
  ["04", "NORMALIZE", "FORMATS / NAMES / TYPES"],
  ["05", "VALIDATE", "RULES / QUALITY / LINEAGE"],
  ["06", "READY", "ANALYTICS / AI / DECISIONS"],
] as const;

const faqs = [
  ["What is Rivu?", "Rivu is an AI-native data refinery that turns messy operational data into clean, structured and analytics-ready information."],
  ["What data does it handle?", "CSV, JSON, spreadsheets, exports and other inconsistent datasets can move through the refinement workflow."],
  ["Does it replace our database or warehouse?", "No. Rivu is designed as a refinement layer between raw sources and the systems where teams analyze or operationalize data."],
  ["Can transformations be traced?", "The product model is built around visible transformations, validation and source-to-output context so changes can be reviewed."],
];

function Logo() {
  return <a className="brand" href="#top" aria-label="Rivu AI"><span className="brand-mark"><i/><i/><i/><i/></span><span className="brand-word">Rivu<span>ai</span></span></a>;
}

function Orb({ small = false }: { small?: boolean }) {
  return <div className={small ? "orb orb-small" : "orb"}><span/><i/><b/></div>;
}

function Cube({ large = false }: { large?: boolean }) {
  return <div className={large ? "cube cube-large" : "cube"}>{Array.from({length:6}).map((_,i)=><i key={i}/>)}<b>R</b></div>;
}

export default function Home() {
  const router = useRouter();
  const [menu, setMenu] = useState(false);
  const [activeStage, setActiveStage] = useState(0);
  const [faq, setFaq] = useState(0);
  const [mouse, setMouse] = useState({x:0,y:0});

  useEffect(() => {
    const move = (e: MouseEvent) => setMouse({x:(e.clientX / window.innerWidth - .5) * 16, y:(e.clientY / window.innerHeight - .5) * 12});
    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, []);

  const jump = (id: string) => { setMenu(false); document.getElementById(id)?.scrollIntoView({behavior:"smooth"}); };

  return <main id="top" className="rivu-site">
    <div className="grain"/>
    <nav className="nav">
      <Logo/>
      <div className={menu ? "nav-menu open" : "nav-menu"}>
        <button onClick={()=>jump("capabilities")}>01 <span>Capabilities</span></button>
        <button onClick={()=>jump("engine")}>02 <span>Engine</span></button>
        <button onClick={()=>jump("quality")}>03 <span>Quality</span></button>
        <button onClick={()=>jump("faq")}>04 <span>FAQ</span></button>
      </div>
      <div className="nav-right">
        <button className="nav-login" onClick={()=>router.push("/login")}>ENTER RIVU <ArrowUpRight size={14}/></button>
        <button className="nav-menu-btn" onClick={()=>setMenu(!menu)}>{menu?<X size={18}/>:<Menu size={18}/>}</button>
      </div>
    </nav>

    <section className="hero">
      <div className="hero-left">
        <div className="eyebrow"><b/> AI-NATIVE DATA REFINERY</div>
        <h1>Make messy<br/><em>data useful.</em></h1>
        <p>Rivu is the intelligent layer between raw information and the systems that depend on it.</p>
        <div className="hero-actions"><button className="primary" onClick={()=>jump("engine")}>Explore Rivu <ArrowDownRight size={16}/></button><button className="text-link" onClick={()=>router.push("/login")}>Open workspace <ArrowUpRight size={15}/></button></div>
      </div>
      <div className="hero-art" style={{"--mx":mouse.x+"px","--my":mouse.y+"px"} as React.CSSProperties}>
        <div className="art-label"><b>RIVU ENGINE</b><span>RAW → REFINED → READY</span></div>
        <div className="art-grid"/>
        <div className="art-ring ring-a"/><div className="art-ring ring-b"/><div className="art-ring ring-c"/>
        <div className="data-stream s1"/><div className="data-stream s2"/><div className="data-stream s3"/>
        <div className="raw-card"><small>RAW INPUT</small><strong>messy_data.csv</strong><span>14,238 rows</span></div>
        <div className="refine-card"><div className="mini-logo">R</div><small>REFINING</small><strong>schema detected</strong><span>duplicates resolved</span><span>types normalized</span></div>
        <Orb/><Orb small/><Cube/>
        <div className="art-word">RIVU</div>
      </div>
      <div className="hero-bottom"><span>SCROLL TO EXPLORE</span><i/></div>
    </section>

    <section className="intro" id="capabilities">
      <div className="section-kicker">01 — THE REFINERY</div>
      <div className="intro-head"><h2>The messy middle<br/><em>is where we work.</em></h2><p>Modern teams have more data than ever. Rivu gives that data a controlled path from uncertainty to usable intelligence.</p></div>
      <div className="capabilities">{capabilities.map(([n,title,text,Icon])=><article className="capability" key={n}><div className="cap-top"><span>{n}</span><Icon size={21}/></div><h3>{title}</h3><p>{text}</p><ArrowUpRight className="cap-arrow" size={17}/></article>)}</div>
    </section>

    <section className="engine" id="engine">
      <div className="engine-top"><div><div className="section-kicker light">02 — THE RIVU ENGINE</div><h2>One flow.<br/><em>Every layer.</em></h2></div><p>Move through the refinery stage by stage. The interface stays simple while the data work underneath stays rigorous.</p></div>
      <div className="stage-nav">{stages.map((s,i)=><button key={s[0]} className={activeStage===i?"active":""} onClick={()=>setActiveStage(i)}><span>{s[0]}</span><b>{s[1]}</b><ChevronRight size={14}/></button>)}</div>
      <div className="engine-visual">
        <div className="big-word">REFINE</div><div className="orbit o1"/><div className="orbit o2"/><div className="orbit o3"/>
        <div className="engine-core"><Cube large/><Orb small/></div>
        <div className="stage-panel"><small>ACTIVE STAGE</small><b>{stages[activeStage][1]}</b><span>{stages[activeStage][2]}</span><div><i/><i/><i/><i/></div></div>
        <div className="line-copy">SOURCE<br/><span>TRANSFORM</span><br/>OUTPUT</div>
      </div>
      <div className="engine-foot"><span>RAW</span><i/><span>UNDERSTAND</span><i/><span>TRANSFORM</span><i/><span>TRUST</span></div>
    </section>

    <section className="quality" id="quality">
      <div className="quality-copy"><div className="section-kicker">03 — QUALITY INTELLIGENCE</div><h2>Know what changed.<br/><em>Know why.</em></h2><p>Rivu treats data quality as part of the product experience — not a report you discover after the damage is done.</p><div className="quality-list"><span><b>01</b> Traceable transformations</span><span><b>02</b> Validation before delivery</span><span><b>03</b> Source-aware outputs</span></div></div>
      <div className="quality-art"><div className="quality-mesh"/><div className="quality-disc"><span>QUALITY</span><b>INTELLIGENCE</b></div>{[1,2,3,4].map(i=><i className={"qorbit q"+i} key={i}/>)}</div>
    </section>

    <section className="manifesto">
      <div className="manifesto-art"><div className="manifesto-shape"/><div className="manifesto-mark">RIVU<br/><small>DATA REFINERY</small></div><span>04 / MESSY MIDDLE</span></div>
      <div className="manifesto-copy"><div className="section-kicker">BUILT FOR THE MESSY MIDDLE</div><h2>Data is not a file.<br/><em>It is a system.</em></h2><p>Sources change. Formats drift. Teams add context. Systems disagree. Rivu gives that movement a consistent refinement layer.</p><button className="primary" onClick={()=>jump("faq")}>Read the principles <ArrowDownRight size={16}/></button></div>
    </section>

    <section className="faq-section" id="faq">
      <div><div className="section-kicker">05 — QUESTIONS</div><h2>Simple answers.<br/><em>No noise.</em></h2></div>
      <div className="faq-list">{faqs.map(([q,a],i)=><div className={faq===i?"faq-item open":"faq-item"} key={q}><button onClick={()=>setFaq(faq===i?-1:i)}><span><small>0{i+1}</small>{q}</span><ChevronDown size={18}/></button><div className="answer"><p>{a}</p></div></div>)}</div>
    </section>

    <section className="closing">
      <div className="closing-grid"/><div className="closing-orb"/>
      <div className="section-kicker light">RIVU BY WATERTING</div><h2>Your data.<br/><em>Finally ready.</em></h2><p>Turn the messy middle into a reliable intelligence layer.</p><button className="closing-button" onClick={()=>router.push("/login")}>Enter Rivu <ArrowUpRight size={16}/></button><div className="closing-word">RIVU</div>
    </section>

    <footer><Logo/><span>AI-native data refinery</span><span>© 2026 WaterTing</span><button onClick={()=>jump("top")}>BACK TO TOP ↑</button></footer>
  </main>;
}
