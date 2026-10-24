"use client";

import Link from "next/link";
import type { CSSProperties } from "react";

export default function BrandLogo({href="/", className=""}:{href?:string;className?:string}) {
  const mark: CSSProperties = {width:31,height:31,display:"grid",gridTemplateColumns:"repeat(2,1fr)",gap:3,position:"relative",flexShrink:0,border:0,borderRadius:0,margin:0};
  const bar: CSSProperties = {display:"block",borderRadius:1,transform:"skewY(-18deg)"};
  return (
    <Link href={href} aria-label="Rivu home" className={className}
      style={{display:"inline-flex",alignItems:"center",gap:10,color:"#fff",textDecoration:"none",fontFamily:"Space Grotesk, Arial, sans-serif",fontSize:29,fontWeight:700,letterSpacing:"-.06em"}}>
      <span style={mark}>
        <i style={{...bar,background:"#fff"}}/><i style={{...bar,background:"#a855f7"}}/>
        <i style={{...bar,background:"#a855f7"}}/><i style={{...bar,background:"#fff"}}/>
      </span>
      <span style={{color:"#fff"}}>rivu<span style={{fontWeight:400,color:"#a855f7"}}>ai</span></span>
    </Link>
  );
}
