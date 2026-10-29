"use client";

import { ChangeEvent, useMemo, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Check, Download, FileSpreadsheet, FileUp, LoaderCircle, Search, ShieldCheck, WandSparkles, LogOut } from "lucide-react";
import { API, catalogueFetch } from "../../../lib/api";
import styles from "./catalogue.module.css";

type Mapping = { source_column: string; target_field: string; confidence: number; transform?: string | null };
type Issue = { field: string; severity: string; message: string };
type Product = { id: string; name: string; sku: string; source_row?: number; brand?: string | null; category?: string | null; description?: string | null; price: number; currency: string; stock_quantity: number; barcode?: string | null; validation_status: string; validation_issues: Issue[]; [key: string]: unknown };
type Template = { id: string; name: string; fields: { name: string; required: boolean }[] };
type UploadData = { catalogue_id: string; original_filename: string; file_format: string; row_count: number; columns: string[]; raw_records: Record<string, unknown>[]; sample_records: Record<string, unknown>[]; suggested_mappings: Mapping[]; available_templates: Template[]; sheet_names?: string[]; selected_sheet?: string };
const TARGETS = ["ignore", "name", "sku", "barcode", "brand", "category", "subcategory", "description", "short_description", "price", "sale_price", "cost_price", "currency", "stock_quantity", "unit_of_measure", "weight", "dimensions", "color", "size", "material", "image_url", "tags", "seo_title", "seo_description"];
const LABELS: Record<string, string> = { name: "Product name", sku: "SKU", barcode: "Barcode", brand: "Brand", category: "Category", subcategory: "Subcategory", description: "Description", short_description: "Short description", price: "Price", sale_price: "Sale price", cost_price: "Cost price", currency: "Currency", stock_quantity: "Stock", unit_of_measure: "Unit", weight: "Weight", dimensions: "Dimensions", color: "Color", size: "Size", material: "Material", image_url: "Image URL", tags: "Tags", seo_title: "SEO title", seo_description: "SEO description" };

async function readJson<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.message || data?.message || `Request failed (${response.status})`);
  }
  return data as T;
}

export default function CatalogueDataEntryPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [upload, setUpload] = useState<UploadData | null>(null);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateId, setTemplateId] = useState("standard_ecommerce");
  const [format, setFormat] = useState("csv");
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [exported, setExported] = useState("");

  async function submitPortalAuth(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const path = authMode === "signup" ? "/catalogue/auth/signup" : "/catalogue/auth/login";
    const body = authMode === "signup"
      ? { email: authEmail, password: authPassword, display_name: displayName, workspace_name: workspaceName }
      : { email: authEmail, password: authPassword };
    try {
      const response = await fetch(API + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await readJson<{ tokens: { access_token: string; refresh_token: string } }>(response);
      localStorage.setItem("catalogue_access_token", data.tokens.access_token);
      localStorage.setItem("catalogue_refresh_token", data.tokens.refresh_token);
      setIsAuthenticated(true);
    } catch (e) { setError(e instanceof Error ? e.message : "Catalogue Portal sign-in failed."); }
    finally { setBusy(false); }
  }

  async function signOut() {
    try { await catalogueFetch("/catalogue/auth/logout", { method: "POST" }); } catch {}
    localStorage.removeItem("catalogue_access_token"); localStorage.removeItem("catalogue_refresh_token");
    setIsAuthenticated(false); setUpload(null); setProducts([]);
  }

  const summary = useMemo(() => ({
    valid: products.filter(p => p.validation_status === "valid").length,
    warning: products.filter(p => p.validation_status === "warning").length,
    error: products.filter(p => p.validation_status === "error").length,
  }), [products]);
  const visible = useMemo(() => products.map((product, index) => ({ product, index })).filter(({ product }) => {
    const match = `${product.name} ${product.sku} ${product.brand || ""}`.toLowerCase().includes(query.toLowerCase());
    return match && (filter === "all" || product.validation_status === filter);
  }), [products, query, filter]);

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setSourceFile(file);
    setBusy(true); setError(""); setNotice(""); setPreview(null); setExported(""); setStage("Uploading and inspecting catalogue");
    try {
      const form = new FormData(); form.append("file", file);
      const parsed = await readJson<UploadData>(await catalogueFetch("/catalogue/upload", { method: "POST", body: form }));
      if (!parsed.raw_records?.length) throw new Error("The file was parsed but contained no product rows.");
      setUpload(parsed); setMappings(parsed.suggested_mappings); setTemplates(parsed.available_templates || []);
      setTemplateId(parsed.available_templates?.[0]?.id || "standard_ecommerce");
      setStage("Applying suggested field mappings");
      const mapped = await readJson<{ products: Product[] }>(await catalogueFetch("/catalogue/map", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ catalogue_id: parsed.catalogue_id, raw_records: parsed.raw_records, mappings: parsed.suggested_mappings, template_id: parsed.available_templates?.[0]?.id || "standard_ecommerce" }) }));
      setProducts(mapped.products); setSelected(0); setNotice(`${parsed.row_count.toLocaleString()} rows parsed. Review the suggested mappings and validation results.`);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not process this catalogue."); }
    finally { setBusy(false); setStage(""); event.target.value = ""; }
  }

  async function changeSheet(sheetName: string) {
    if (!sourceFile || busy) return;
    setBusy(true); setError(""); setStage(`Reading sheet ${sheetName}`);
    try {
      const form = new FormData(); form.append("file", sourceFile); form.append("sheet_name", sheetName);
      const parsed = await readJson<UploadData>(await catalogueFetch("/catalogue/upload", { method: "POST", body: form }));
      setUpload(parsed); setMappings(parsed.suggested_mappings);
      const result = await readJson<{ products: Product[] }>(await catalogueFetch("/catalogue/map", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ catalogue_id: parsed.catalogue_id, raw_records: parsed.raw_records, mappings: parsed.suggested_mappings, template_id: templateId }) }));
      setProducts(result.products); setSelected(0); setPreview(null); setNotice(`${parsed.row_count.toLocaleString()} rows loaded from ${sheetName}.`);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not read that workbook sheet."); }
    finally { setBusy(false); setStage(""); }
  }

  async function handleTargetTemplate(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true); setError(""); setStage("Inspecting target template");
    try {
      const form = new FormData(); form.append("file", file);
      const parsed = await readJson<UploadData>(await catalogueFetch("/catalogue/upload", { method: "POST", body: form }));
      const targetMappings = new Map(parsed.suggested_mappings.filter(mapping => !mapping.target_field.startsWith("custom:")).map(mapping => [mapping.source_column, mapping.target_field]));
      const template = await readJson<Template>(await catalogueFetch("/catalogue/templates", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: `custom_${Date.now()}`, name: `${file.name.replace(/\.[^.]+$/, "")} import template`, description: `Target fields detected from ${file.name}`, platform: "custom", fields: parsed.columns.map(name => ({ name, label: name, data_type: "string", required: ["name", "sku", "price"].includes(targetMappings.get(name) || ""), mapped_to: targetMappings.get(name) || `custom:${name}` })) }) }));
      setTemplates(current => [...current.filter(item => item.id !== template.id), template]);
      const result = await readJson<{ products: Product[] }>(await catalogueFetch("/catalogue/map", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ catalogue_id: upload?.catalogue_id, raw_records: upload?.raw_records || [], mappings, template_id: template.id }) }));
      if (upload) setProducts(result.products);
      setTemplateId(template.id); setPreview(null);
      setNotice(`Target template saved from ${file.name}. Required fields and column names are ready for export.`);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not read the target template."); }
    finally { setBusy(false); setStage(""); event.target.value = ""; }
  }

  async function applyMappings(nextMappings = mappings, nextTemplate = templateId) {
    if (!upload || busy) return;
    setBusy(true); setError(""); setStage("Mapping fields and validating rows");
    try {
      const result = await readJson<{ products: Product[] }>(await catalogueFetch("/catalogue/map", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ catalogue_id: upload.catalogue_id, raw_records: upload.raw_records, mappings: nextMappings, template_id: nextTemplate }) }));
      setMappings(nextMappings); setTemplateId(nextTemplate); setProducts(result.products); setSelected(0); setPreview(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Mapping failed."); }
    finally { setBusy(false); setStage(""); }
  }

  async function revalidate(nextProducts: Product[]) {
    setProducts(nextProducts); setPreview(null); setExported("");
    try {
      const result = await readJson<{ products: Product[] }>(await catalogueFetch("/catalogue/validate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ catalogue_id: upload?.catalogue_id, products: nextProducts, template_id: templateId }) }));
      setProducts(result.products);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not revalidate products."); }
  }

  function editProduct(index: number, field: string, value: string) {
    const updated = products.map((product, i) => i === index ? { ...product, [field]: ["price", "sale_price", "cost_price", "stock_quantity", "weight"].includes(field) ? (value === "" ? 0 : Number(value)) : value } : product);
    setProducts(updated); setPreview(null); setExported("");
  }

  async function createPreview() {
    setBusy(true); setError(""); setStage("Preparing target preview");
    try {
      const response = await readJson<Record<string, unknown>>(await catalogueFetch("/catalogue/export/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ catalogue_id: upload?.catalogue_id, products: products.filter(p => p.validation_status !== "error"), template_id: templateId, format }) }));
      setPreview(response); setNotice("Preview includes valid and warning rows. Error rows are excluded.");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not prepare preview."); }
    finally { setBusy(false); setStage(""); }
  }

  async function exportFile() {
    setBusy(true); setError(""); setStage(`Preparing ${format.toUpperCase()} download`);
    try {
      const response = await catalogueFetch("/catalogue/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ catalogue_id: upload?.catalogue_id, products: products.filter(p => p.validation_status !== "error"), template_id: templateId, format }) });
      if (!response.ok) await readJson(response);
      const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement("a");
      const disposition = response.headers.get("content-disposition") || ""; const match = disposition.match(/filename="([^"]+)"/);
      link.href = url; link.download = match?.[1] || `rivu_catalogue.${format}`; link.click(); URL.revokeObjectURL(url);
      setExported(link.download); setNotice(`${summary.error} invalid row(s) skipped. ${products.length - summary.error} records exported.`);
    } catch (e) { setError(e instanceof Error ? e.message : "Export failed."); }
    finally { setBusy(false); setStage(""); }
  }

  if (!isAuthenticated && !(typeof window !== "undefined" && window.localStorage.getItem("catalogue_access_token"))) {
    return <main className={styles.page}><header className={styles.top}><Link href="/our-services"><ArrowLeft size={16}/> Our Services</Link><span>CATALOGUE PORTAL / SECURE ENTRY</span><span className={styles.secure}><ShieldCheck size={15}/> Separate workspace</span></header><section className={styles.signin}><ShieldCheck size={28}/><p className={styles.kicker}>STANDALONE CATALOGUE WORKSPACE</p><h1>{authMode === "login" ? "Sign in to your catalogue" : "Create your catalogue workspace"}</h1><p>This account and its catalogue data are separate from Rivu Data Refinery.</p><form className={styles.authForm} onSubmit={submitPortalAuth}>{authMode === "signup" && <><label>Full name<input required minLength={2} maxLength={200} value={displayName} onChange={e => setDisplayName(e.target.value)} autoComplete="name"/></label><label>Workspace name<input required minLength={2} maxLength={200} value={workspaceName} onChange={e => setWorkspaceName(e.target.value)} placeholder="Acme Product Catalog"/></label></>}<label>Email<input required type="email" value={authEmail} onChange={e => setAuthEmail(e.target.value)} autoComplete="email"/></label><label>Password<input required type="password" minLength={authMode === "signup" ? 10 : 1} value={authPassword} onChange={e => setAuthPassword(e.target.value)} autoComplete={authMode === "signup" ? "new-password" : "current-password"}/></label>{error && <div className={styles.alert} role="alert">{error}</div>}<button disabled={busy}>{busy ? "Connecting…" : authMode === "login" ? "Sign in to Catalogue Portal" : "Create separate workspace"}</button></form><button className={styles.authToggle} onClick={() => { setError(""); setAuthMode(authMode === "login" ? "signup" : "login"); }}>{authMode === "login" ? "New here? Create a separate workspace" : "Already have a Catalogue Portal account? Sign in"}</button><p className={styles.authFootnote}>Separate catalogue login, JWT signing key, workspace records, and database.</p></section></main>;
  }

  return <main className={styles.page}>
    <header className={styles.top}><Link href="/our-services"><ArrowLeft size={16}/> Our Services</Link><span>CATALOGUE PORTAL / PRODUCT DATA</span><span className={styles.secure}><ShieldCheck size={15}/> Separate workspace</span><button className={styles.signOut} onClick={signOut}><LogOut size={14}/> Sign out</button></header>
    <section className={styles.heading}><div><p className={styles.kicker}>OUR SOLUTIONS / PRODUCT DATA</p><h1>Catalogue <em>Data Entry</em></h1><p>Map supplier catalogue fields, resolve data issues, and prepare a reviewed import file.</p></div><Link href="/services">Open Data Studio ↗</Link></section>
    {error && <div className={styles.alert} role="alert"><AlertCircle size={17}/>{error}</div>}{notice && <div className={styles.notice}><Check size={16}/>{notice}</div>}
    <section className={styles.uploadPanel}><div><span className={styles.step}>01 / SOURCE</span><h2>Upload supplier catalogue</h2><p>CSV, XLSX, XLS, JSON or text-based PDF. Scanned PDFs need OCR and will be reported as unsupported.</p></div><label className={styles.uploadButton}><input type="file" accept=".csv,.xlsx,.xls,.json,.pdf" onChange={handleUpload} disabled={busy}/><FileUp size={17}/>{busy ? stage : upload ? "Choose another file" : "Choose catalogue"}</label>{upload && <div className={styles.fileInfo}><b>{upload.original_filename}</b><span>{upload.file_format.toUpperCase()} · {upload.row_count.toLocaleString()} rows · {upload.columns.length} columns{upload.sheet_names?.length ? ` · ${upload.sheet_names.length} sheets` : ""}</span></div>}</section>
    {upload && <>
      {upload.sheet_names && upload.sheet_names.length > 1 && <section className={styles.sheetPicker}><label>Workbook sheet<select value={upload.selected_sheet || upload.sheet_names[0]} disabled={busy} onChange={e => void changeSheet(e.target.value)}>{upload.sheet_names.map(sheet => <option key={sheet}>{sheet}</option>)}</select></label></section>}
      <section className={styles.section}><div className={styles.sectionHead}><div><span className={styles.step}>02 / MAP</span><h2>Review field mapping</h2><p>Automatic suggestions can be changed before processing.</p></div><button disabled={busy} onClick={() => void applyMappings()}><WandSparkles size={15}/> Apply mappings</button></div>
        <div className={styles.mappingGrid}>{mappings.map((mapping, index) => <label key={mapping.source_column} className={styles.mapping}><span>{mapping.source_column}</span><select value={mapping.target_field} onChange={e => setMappings(current => current.map((item, i) => i === index ? { ...item, target_field: e.target.value, transform: e.target.value === "ignore" ? null : item.transform } : item))}><option value={mapping.target_field}>{mapping.target_field.startsWith("custom:") ? `Keep as ${mapping.target_field.slice(7)}` : LABELS[mapping.target_field] || mapping.target_field}</option>{TARGETS.map(target => <option key={target} value={target}>{LABELS[target] || (target === "ignore" ? "Ignore column" : target)}</option>)}<option value={`custom:${mapping.source_column}`}>Keep as custom attribute</option></select><small>{Math.round(mapping.confidence * 100)}% match</small></label>)}</div>
      </section>
      <section className={styles.section}><div className={styles.sectionHead}><div><span className={styles.step}>03 / REVIEW</span><h2>Product records</h2><p>Correct values directly, then revalidate the changed catalogue.</p></div><div className={styles.reviewActions}><div className={styles.stats}><span className={styles.valid}>{summary.valid} valid</span><span className={styles.warning}>{summary.warning} warnings</span><span className={styles.invalid}>{summary.error} errors</span></div><button disabled={busy} onClick={() => void revalidate(products)}>Revalidate records</button></div></div>
        <div className={styles.toolbar}><label className={styles.search}><Search size={15}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search product, SKU, brand"/></label><select value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All records ({products.length})</option><option value="error">Errors ({summary.error})</option><option value="warning">Warnings ({summary.warning})</option><option value="valid">Valid ({summary.valid})</option></select></div>
        <div className={styles.tableWrap}><table><thead><tr><th>Row</th><th>Status</th><th>Product name</th><th>SKU</th><th>Price</th><th>Stock</th><th>Issues</th></tr></thead><tbody>{visible.slice(0, 250).map(({ product, index }) => <tr key={product.id} className={index === selected ? styles.selected : ""} onClick={() => setSelected(index)}><td>{product.source_row || index + 1}</td><td><span className={`${styles.status} ${styles[product.validation_status]}`}>{product.validation_status}</span></td><td><input aria-label={`Product name row ${index + 1}`} value={product.name} onChange={e => editProduct(index, "name", e.target.value)} onClick={e => e.stopPropagation()}/></td><td><input aria-label={`SKU row ${index + 1}`} value={product.sku} onChange={e => editProduct(index, "sku", e.target.value)} onClick={e => e.stopPropagation()}/></td><td><input aria-label={`Price row ${index + 1}`} type="number" min="0" step="0.01" value={product.price} onChange={e => editProduct(index, "price", e.target.value)} onClick={e => e.stopPropagation()}/></td><td><input aria-label={`Stock row ${index + 1}`} type="number" value={product.stock_quantity} onChange={e => editProduct(index, "stock_quantity", e.target.value)} onClick={e => e.stopPropagation()}/></td><td>{product.validation_issues?.length || 0}</td></tr>)}</tbody></table>{visible.length > 250 && <p className={styles.limit}>Showing the first 250 matches. Refine the search to find other records.</p>}{visible.length === 0 && <p className={styles.limit}>No products match these filters.</p>}</div>
        {products[selected] && <div className={styles.details}><div><span className={styles.step}>ROW {products[selected].source_row || selected + 1} / PRODUCT DETAILS</span><h3>{products[selected].name || "Unnamed product"}</h3><p>Source data stays unchanged in this session; edit the mapped product and revalidate when ready.</p></div><div className={styles.detailGrid}>{(["brand", "category", "barcode", "currency", "description"] as const).map(field => <label key={field}>{LABELS[field]}<input value={String(products[selected][field] ?? "")} onChange={e => editProduct(selected, field, e.target.value)}/></label>)}</div><div className={styles.comparison}><div><h4>Original source row</h4><pre>{JSON.stringify(upload.raw_records[(products[selected].source_row || selected + 1) - 1] || {}, null, 2)}</pre></div><div><h4>Current mapped values</h4><pre>{JSON.stringify({ name: products[selected].name, sku: products[selected].sku, brand: products[selected].brand, category: products[selected].category, price: products[selected].price, currency: products[selected].currency, stock_quantity: products[selected].stock_quantity, barcode: products[selected].barcode }, null, 2)}</pre></div></div>{products[selected].validation_issues?.length ? <ul className={styles.issues}>{products[selected].validation_issues.map((issue, i) => <li key={`${issue.field}-${i}`}><b>{issue.field}</b> {issue.message}</li>)}</ul> : <p className={styles.noIssues}><Check size={15}/> No validation issues</p>}</div>}
      </section>
      <section className={styles.section}><div className={styles.sectionHead}><div><span className={styles.step}>04 / OUTPUT</span><h2>Target template & export</h2><p>Export errors are skipped; warning rows remain included for review.</p></div><label className={styles.templateUpload}>Use an import template<input type="file" accept=".csv,.xlsx,.xls,.json,.pdf" onChange={handleTargetTemplate} disabled={busy}/></label></div><div className={styles.exportControls}><label>Target format<select value={templateId} onChange={e => void applyMappings(mappings, e.target.value)}>{templates.map(template => <option key={template.id} value={template.id}>{template.name}</option>)}</select></label><label>File type<select value={format} onChange={e => { setFormat(e.target.value); setPreview(null); }}><option value="csv">CSV</option><option value="xlsx">XLSX</option><option value="json">JSON</option></select></label><button className={styles.secondary} disabled={busy || summary.valid + summary.warning === 0} onClick={createPreview}><FileSpreadsheet size={16}/> Preview output</button><button className={styles.primary} disabled={busy || summary.valid + summary.warning === 0 || !preview} onClick={exportFile}><Download size={16}/> Export {format.toUpperCase()}</button></div>
        {busy && <p className={styles.progress}><LoaderCircle size={16}/>{stage}</p>}{preview && <div className={styles.preview}><div><b>{String(preview.template_name)} · {String(preview.format).toUpperCase()}</b><span>{products.length - summary.error} included · {summary.error} error rows skipped</span></div><pre>{JSON.stringify({ columns: preview.output_columns, sample: preview.sample_rows }, null, 2)}</pre></div>}{exported && <p className={styles.downloaded}><Check size={16}/> Downloaded {exported}</p>}
      </section>
      <footer className={styles.footer}><span>Original file: {upload.original_filename}</span><span>{products.length.toLocaleString()} rows in this session</span></footer>
    </>}
  </main>;
}
