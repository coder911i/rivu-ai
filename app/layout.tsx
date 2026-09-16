import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata={title:"Rivu AI — From messy data to intelligence",description:"AI-native data refinery by WaterTing"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
