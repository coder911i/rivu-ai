"use client";
import type { CSSProperties } from "react";
const stages=["Scanning","Profiling","Detecting","Cleaning","Validating","Generating"];
export default function ProcessingRail({active=false,label="Processing"}:{active?:boolean;label?:string}){
 if(!active) return null;
 return <div className="rivuProcessing" role="status" aria-live="polite"><div className="rivuProcessingHead"><span>{label}</span><span className="rivuProcessingPulse"/></div><div className="rivuStages">{stages.map((s,i)=><span key={s} style={{"--i":i} as CSSProperties}>{s}</span>)}</div></div>;
}