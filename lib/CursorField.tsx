"use client";
import { useEffect, useRef } from "react";

export default function CursorField(){
  const ref=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const el=ref.current;
    if(!el || !window.matchMedia("(pointer:fine)").matches || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const onMove=(e:PointerEvent)=>{
      el.style.setProperty("--mx", e.clientX+"px");
      el.style.setProperty("--my", e.clientY+"px");
    };
    window.addEventListener("pointermove",onMove,{passive:true});
    return()=>window.removeEventListener("pointermove",onMove);
  },[]);
  return <div ref={ref} className="rivuCursorField" aria-hidden="true"><span/><span/><span/><span/><span/><span/><span/><span/><span/></div>;
}