'use client';

import React, { useEffect, useMemo, useState, useRef } from 'react';
import { Dialog, DialogContent } from '@operation-room/components/ui/dialog';
import { useStudioStore } from '../store/useStudioStore';
import { api } from '@operation-room/lib/api';
import { Shield } from 'lucide-react';
import NextImage from 'next/image';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, CartesianGrid, Sector, Legend } from 'recharts';

interface GhostWriterWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  caseId: string;
  docId: string;
  apiBaseUrl?: string;
  exportEngine?: 'standard' | 'dynamite';
  exportFormat?: 'pdf' | 'docx';
  onExportComplete?: (result: any) => void;
}

type StreamBlock =
  | { new_page_index: number; new_type: 'title' | 'paragraph'; new_text: string; }
  | { new_page_index: number; new_type: 'chart'; new_chart: any; }
  | { new_page_index: number; new_type: 'table'; new_table: any; }
  | { new_page_index: number; new_type: 'list'; new_list: any; };

export function GhostWriterWizard({ open, onOpenChange, caseId, docId, apiBaseUrl, exportEngine = 'standard', exportFormat = 'pdf', onExportComplete }: GhostWriterWizardProps) {
  const pages = useStudioStore(state => state.pages);
  const documentTitle = useStudioStore(state => state.documentTitle);    const focusMode = useStudioStore(state => state.focusMode);
  const [new_templates, setNewTemplates] = useState<any[]>([]);
  const [new_selected_template, setNewSelectedTemplate] = useState('');
  const [new_selected_cover, setNewSelectedCover] = useState('');

  useEffect(() => {
    api.get(`/v4/studio/cases/${caseId}/templates`)
      .then((data) => {
        const list = data.templates || [];
        setNewTemplates(list);
        if (list.length > 0) {
          setNewSelectedTemplate(list[0].id);
          setNewFontStyle(list[0].fonts?.[0]?.id || 'times');
          setNewGraphStyle(list[0].graphs?.[0]?.id || 'classic');
          setNewTableStyle(list[0].tables?.[0]?.id || 'clean');
        }
      })
      .catch(console.error);
  }, []);

  const new_available_graphs = [
      { id: 'timeline', name: 'Risk Time (Line)' },
      { id: 'top_entities', name: 'Entities (Horiz)' },
      { id: 'signals', name: 'Behaviors (Bar)' },
      { id: 'file_types', name: 'File Types (Pie)' },
      { id: 'scores', name: 'Scores (Hist)' },
      { id: 'integrity', name: 'Integrity (Bar)' },
      { id: 'parse_errors', name: 'Errors (Bar)' },
      { id: 'duckdb', name: 'Database (Bar)' }
  ];

  const new_toggle_graph = (new_id: string) => {
      if (new_selected_graphs.includes(new_id)) {
          if (new_selected_graphs.length <= 1) {
              setNewError("You must select at least 1 graph type.");
              setTimeout(() => setNewError(''), 2000);
              return;
          }
          setNewSelectedGraphs(new_prev => new_prev.filter(new_g => new_g !== new_id));
      } else {
          if (new_selected_graphs.length >= 5) {
              setNewError("Maximum 5 graph types allowed for optimal layout.");
              setTimeout(() => setNewError(''), 2000);
              return;
          }
          setNewSelectedGraphs(new_prev => [...new_prev, new_id]);
      }
  };

  const new_active_template_obj = useMemo(() => new_templates.find(t => t.id === new_selected_template), [new_templates, new_selected_template]);
  
  const [new_setup_step, setNewSetupStep] = useState<'template' | 'cover' | 'customize'>('template');
  const [new_font_style, setNewFontStyle] = useState('times');
  const [new_graph_style, setNewGraphStyle] = useState('classic');
  const [new_table_style, setNewTableStyle] = useState('clean');
  const [new_custom_tab, setNewCustomTab] = useState<'fonts' | 'graphs' | 'tables'>('fonts');

  const new_font_family = new_font_style === "times" ? "'Times New Roman', serif" : new_font_style === "georgia" ? "'Georgia', serif" : "'Inter', sans-serif";
  const new_primary_color = new_selected_cover === "1" ? "#0F172A" : new_selected_cover === "2" ? "#312e81" : "#4c0519";
  const new_mock_palette = new_graph_style === "classic" ? { bg: "#FFFFFF", grid: "#E2E8F0", c1: "#0284C7", c2: "#38BDF8", c3: "#0EA5E9", c4: "#7DD3FC", text: "#334155" } : new_graph_style === "modern" ? { bg: "#F8FAFC", grid: "#CBD5E1", c1: "#4F46E5", c2: "#818CF8", c3: "#6366F1", c4: "#A5B4FC", text: "#1E293B" } : { bg: "#0F172A", grid: "#334155", c1: "#38BDF8", c2: "#BAE6FD", c3: "#0EA5E9", c4: "#7DD3FC", text: "#F8FAFC" };

  const [new_selected_graphs, setNewSelectedGraphs] = useState<string[]>(['timeline', 'file_types']);

  const [new_phase, setNewPhase] = useState<'idle' | 'writing' | 'compiling' | 'done'>('idle');
  const [new_pdf_url, setNewPdfUrl] = useState('');
  const [new_loading, setNewLoading] = useState(false);
  const [new_error, setNewError] = useState('');
  
  const [new_stream_index, setNewStreamIndex] = useState(0);
  const [new_stream_char, setNewStreamChar] = useState(0);

  const scrollRef = useRef<HTMLDivElement>(null);
  const userScrolled = useRef(false);

  const handleScroll = (e: any) => {
      const t = e.target;
      userScrolled.current = (t.scrollHeight - t.scrollTop - t.clientHeight) > 150;
  };

  useEffect(() => {
    if (open) {
      setNewPhase('idle');
      setNewSetupStep('template');
      setNewPdfUrl('');
      setNewError('');
      setNewStreamIndex(0);
      setNewStreamChar(0);
    }
  }, [open]);

  // Convert NFLIP Canvas elements strictly into typing blocks for the preview animation
  const new_stream_blocks = useMemo<StreamBlock[]>(() => {
    const arr: StreamBlock[] = [];
    pages.slice(0, 5).forEach((page, pageIndex) => {
        arr.push({ new_page_index: pageIndex, new_type: 'title', new_text: documentTitle || `Page ${pageIndex + 1}` });
        page.elements.forEach((el) => {
            if (el.type === 'text') {
                const cleanText = el.data?.content?.replace(/<[^>]+>/g, '') || 'Analyzed telemetry block.';
                arr.push({ new_page_index: pageIndex, new_type: 'paragraph', new_text: cleanText });
            } else if (el.type === 'component') {
                const ctype = el.data?.type || 'chart';
                if (ctype === 'chart' || ctype === 'shap-explanation' || ctype === 'anomaly') {
                    arr.push({ 
                        new_page_index: pageIndex, 
                        new_type: 'chart', 
                        new_chart: { type: ctype === 'shap-explanation' ? 'horizontal_bar' : 'line', data: [{name: 'Data 1', value: 40}, {name: 'Data 2', value: 80}] } 
                    });
                }
            }
        });
    });
    return arr;
  }, [pages, documentTitle]);

  useEffect(() => {
    if (new_phase !== 'writing') return;
    if (!new_stream_blocks.length) {
        setNewPhase('compiling'); return;
    }

    if (new_stream_index >= new_stream_blocks.length) {
      const t = setTimeout(() => setNewPhase('compiling'), 600);
      return () => clearTimeout(t);
    }

    const current = new_stream_blocks[new_stream_index];

    if (current.new_type === 'title' || current.new_type === 'paragraph') {
      const text = current.new_text || '';
      if (new_stream_char < text.length) {
        const t = setTimeout(() => setNewStreamChar((v) => v + 1), 8);
        return () => clearTimeout(t);
      } else {
        const t = setTimeout(() => { setNewStreamIndex((v) => v + 1); setNewStreamChar(0); }, 110);
        return () => clearTimeout(t);
      }
    } else {
      const t = setTimeout(() => { setNewStreamIndex((v) => v + 1); setNewStreamChar(0); }, 260);
      return () => clearTimeout(t);
    }
  }, [new_phase, new_stream_blocks, new_stream_index, new_stream_char]);

  // The actual background Playwright trigger
  useEffect(() => {
    if (new_phase === 'compiling') {
        const runExport = async () => {
             try {
                 const isOfflineDoc = String(docId || '').startsWith('local-');
                 const pagesPayload = useStudioStore.getState().pages;
                 const astPayload = {
                   type: 'v4-canvas',
                   version: '1.0',
                   pages: pagesPayload,
                 };

                 const coverImage = new_active_template_obj?.covers?.find((c: any) => c.id === new_selected_cover)?.image || '';
                 const coverId = coverImage ? coverImage.split('/').pop()?.replace('.png', '') || new_selected_cover : new_selected_cover;

                  const result = await api.post(`/v4/studio/cases/${caseId}/exports/${exportFormat}`, {
                      doc_id: docId,
                      actor: 'investigator',
                      frontend_url: window.location.origin,
                      cover_id: coverId,
                     focus_mode: focusMode,
                     engine: exportEngine === 'dynamite' ? 'dynamite' : 'reportlab',
                     font_style: new_font_style,
                      graph_style: exportFormat === 'pdf' ? new_graph_style : undefined,
                      table_style: exportFormat === 'pdf' ? new_table_style : undefined,
                      selected_graphs: exportFormat === 'pdf' ? new_selected_graphs : undefined,
                      ast: isOfflineDoc ? astPayload : undefined,
                      title: isOfflineDoc ? (documentTitle || 'Offline Investigation Report') : undefined,
                   });
                  if (result?.url) {
                      const absoluteUrl = apiBaseUrl && result.url.startsWith('/')
                        ? `${apiBaseUrl}${result.url}`
                        : result.url;
                      setNewPdfUrl(absoluteUrl);
                  }
                 setNewPhase('done');
                 onExportComplete?.(result);
             } catch (err: any) {
                 setNewError(`EXPORT CRASH: ${err.message}`);
                 setNewPhase('idle');
             }
        };
        runExport();
    }
  }, [new_phase, caseId, docId, new_selected_cover, onExportComplete, exportFormat, exportEngine, focusMode, new_font_style, new_graph_style, new_table_style, new_selected_graphs, new_active_template_obj, apiBaseUrl, documentTitle]);

  const startGhostwriter = () => {
    if (!new_selected_template || !new_selected_cover) { setNewError('Missing template selection'); return; }
    setNewError('');
    setNewPhase('writing');
    setNewStreamIndex(0);
    setNewStreamChar(0);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };


  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[100vw] w-screen h-screen max-h-[100vh] p-0 m-0 rounded-none bg-[#F8FAFC] border-none overflow-hidden flex flex-col">
        {/* CSS INJECT */}
        <style>{`
            .table-clean { border-collapse: collapse; width: 100%; }
            .table-clean th { border-bottom: 2px solid #CBD5E1; padding: 12px; text-align: left; }
            .table-clean td { padding: 12px; }
            @keyframes slidein { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            @keyframes blink { 50% { border-color: transparent; } }
        `}</style>

        {/* TOP NAVBAR */}
        <div style={{ padding: "15px 30px", borderBottom: "1px solid #E2E8F0", backgroundColor: "#FFFFFF", display: "flex", alignItems: "center", boxShadow: "0 2px 10px rgba(0,0,0,0.02)" }}>
            <div style={{ fontWeight: "bold", color: "#0F172A", fontSize: "16px", display: "flex", alignItems: "center", gap: "10px" }}>
                <Shield className="h-5 w-5 text-sky-600" /> Ghost Writer Pipeline
            </div>
            <div style={{ marginLeft: "auto", display: "flex", gap: "20px" }}>
                <button onClick={() => onOpenChange(false)} style={{ color: "#64748B", background: "none", border: "none", cursor: "pointer", fontWeight: "bold" }}>Cancel</button>
                {new_phase === 'idle' && new_setup_step === 'customize' && (
                    <button onClick={startGhostwriter} style={{ backgroundColor: "#0284C7", color: "#FFFFFF", padding: "8px 20px", borderRadius: "6px", fontWeight: "bold", border: "none", cursor: "pointer", boxShadow: "0 4px 6px rgba(2, 132, 199, 0.2)" }}>COMPILE REPORT</button>
                )}
            </div>
        </div>

        {/* PIPELINE STEPPER */}
        <div style={{ padding: "15px 30px", borderBottom: "1px solid #E2E8F0", backgroundColor: "#F1F5F9", display: "flex", gap: "20px" }}>
            {['Configure Style', 'Ghostwriting', 'Compiling Ledger', 'Official PDF'].map((txt, i) => {
                const active = (i === 0 && new_phase === 'idle') || (i === 1 && new_phase === 'writing') || (i === 2 && new_phase === 'compiling') || (i === 3 && new_phase === 'done');
                const past = (i === 0 && new_phase !== 'idle') || (i === 1 && (new_phase === 'compiling' || new_phase === 'done')) || (i === 2 && new_phase === 'done');
                return (
                    <div key={i} style={{ display: "flex", alignItems: "center", fontStyle: "italic", flex: 1, color: active || past ? "#0F172A" : "#94A3B8", fontWeight: active ? "bold" : "normal" }}>
                        <div style={{ width: "24px", height: "24px", borderRadius: "50%", background: active ? "#0284C7" : past ? "#10B981" : "#E2E8F0", color: active || past ? "#FFF" : "#94A3B8", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "12px", marginRight: "10px" }}>
                            {past ? "✓" : i + 1}
                        </div>
                        {txt}
                    </div>
                )
            })}
        </div>

        {/* EXPORT ERROR */}
        {new_error && <div className="bg-red-50 border-red-200 text-red-600 p-4 m-4 rounded font-bold">{new_error}</div>}

        {/* MAIN BODY WRAPPER */}
        <div ref={scrollRef} onScroll={handleScroll} style={{ flexGrow: 1, overflowY: "auto", padding: "40px", display: "flex", flexDirection: "column", alignItems: "center", background: "#F8FAFC" }}>

            {/* WRITING PHASE */}
            {new_phase === 'writing' && (
                <div style={{ width: "100%", maxWidth: "900px", padding: "30px", background: "#FFF", borderRadius: "8px", border: "1px solid #E2E8F0", animation: "slidein 0.5s" }}>
                    <h2 style={{ fontSize: "24px", color: "#0F172A", marginBottom: "10px" }}>Ghostwriting in Progress...</h2>
                    <div style={{ padding: "20px", background: "#F1F5F9", borderRadius: "6px", fontFamily: "monospace", fontSize: "14px", whiteSpace: "pre-wrap", color: "#334155" }}>
                        {new_stream_blocks.slice(0, new_stream_index).map(b => (b as any).new_text ? (b as any).new_text + "\n\n" : "[Visual Evidence Block Generated]\n\n").join("")}
                        {((new_stream_blocks[new_stream_index] as any)?.new_text || '[Visual Evidence Block Generated]').substring(0, new_stream_char)}
                        <span style={{ borderRight: "2px solid #0284C7", animation: "blink 1s step-end infinite" }}></span>
                    </div>
                </div>
            )}

            {/* COMPILING PHASE */}
            {new_phase === 'compiling' && (
                <div style={{ width: "100%", maxWidth: "900px", padding: "40px", background: "#FFF", borderRadius: "8px", border: "1px solid #E2E8F0", animation: "slidein 0.5s", display: "flex", flexDirection: "column", alignItems: "center" }}>
                    <h2 style={{ fontSize: "24px", color: "#0F172A", marginBottom: "15px" }}>Compiling Ledger</h2>
                    <p style={{ color: "#64748B", marginBottom: "30px", textAlign: "center" }}>
                        Spinning up Playwright Engine to capture the dossier layout.<br />
                        Please hold tight...
                    </p>
                    <div style={{
                        width: "50px", height: "50px", border: "4px solid #E2E8F0", borderTop: "4px solid #0284C7", borderRadius: "50%", animation: "spin 1s linear infinite"
                    }} />
                    <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
                </div>
            )}

            {/* DONE PHASE */}
            {new_phase === 'done' && (
                <div style={{ width: "100%", maxWidth: "900px", padding: "30px", background: "#FFF", borderRadius: "8px", border: "1px solid #E2E8F0", animation: "slidein 0.5s" }}>
                    <h2 style={{ fontSize: "24px", color: "#0F172A", marginBottom: "10px" }}>Official Dossier Verified</h2>
                    <p style={{ color: "#64748B", marginBottom: "20px" }}>The Ghost Writer engine has completed physical rendering via Playwright Engine.</p>
                    <div style={{ display: "flex", gap: "10px" }}>
                       {new_pdf_url ? (
                           <a href={new_pdf_url} download style={{ background: "#0284C7", color: "#FFF", padding: "12px 24px", borderRadius: "6px", textDecoration: "none", fontWeight: "bold" }}>Download Authentic PDF ↓</a>
                       ) : (
                           <span className="text-emerald-600 font-bold border border-emerald-200 bg-emerald-50 p-3 rounded">Export Successful (Available within Vault)</span>
                       )}
                       <button onClick={() => onOpenChange(false)} style={{ padding: "12px 24px", border: "1px solid #CBD5E1", borderRadius: "6px", fontWeight: "bold" }}>Close Studio</button>
                    </div>
                </div>
            )}

                        {/* TEMPLATE/COVER/CUSTOMIZE (IDLE) */}
            {new_phase === 'idle' && new_setup_step === 'template' && (
              <div style={{ width: "100%", maxWidth: "1000px" }}>
                <h3 style={{ marginBottom: "15px", color: "#0F172A", fontSize: "20px", fontWeight: "bold" }}>1. Select Core Template</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px', marginBottom: '30px' }}>
                  {new_templates.map((new_t: any) => (
                    <div
                      key={new_t.id}
                      onClick={() => { setNewSelectedTemplate(new_t.id); setNewSelectedCover(''); setNewError(''); }}
                      style={{ cursor: 'pointer', border: new_selected_template === new_t.id ? '2px solid #0284C7' : '1px solid #CBD5E1', borderRadius: '8px', padding: '20px', background: '#FFFFFF', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)', transition: 'all 0.2s', transform: new_selected_template === new_t.id ? 'translateY(-2px)' : 'none' }}
                    >
                      <NextImage src={new_t.thumbnail} alt={new_t.name} width={560} height={140} unoptimized style={{ width: "100%", height: "140px", objectFit: "contain", marginBottom: "15px", borderRadius: "4px", backgroundColor: "#F8FAFC", padding: "10px" }} />
                      <div style={{ fontWeight: 'bold', marginBottom: '6px', color: '#0F172A', fontSize: "16px" }}>{new_t.name}</div>
                      <div style={{ color: '#64748B', fontSize: '13px', fontWeight: "bold" }}>Standard Architecture</div>
                    </div>
                  ))}
                </div>

                {new_active_template_obj && (
                  <div style={{ animation: "slidein 0.4s" }}>
                    <h3 style={{ marginBottom: "15px", color: "#0F172A", borderTop: "1px solid #E2E8F0", paddingTop: "20px", fontSize: "20px", fontWeight: "bold" }}>2. Select Cover Layout</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', marginBottom: '30px' }}>
                      {(new_active_template_obj.covers || []).map((new_c: any) => (
                        <div
                          key={new_c.id}
                          onClick={() => setNewSelectedCover(new_c.id)}
                          style={{ cursor: 'pointer', border: new_selected_cover === new_c.id ? '2px solid #0284C7' : '1px solid #CBD5E1', borderRadius: '8px', padding: '15px', background: '#FFFFFF', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)', textAlign: 'center', transition: "all 0.2s" }}
                        >
                          <NextImage src={new_c.image} alt={new_c.name} width={400} height={260} unoptimized style={{ width: '100%', height: '260px', objectFit: 'contain', borderRadius: '4px', marginBottom: '15px', background: '#F8FAFC', padding: "5px", border: "1px solid #E2E8F0" }} />
                          <div style={{ fontWeight: 'bold', color: '#0F172A' }}>{new_c.name}</div>
                        </div>
                      ))}
                    </div>
                    
                    <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "20px" }}>
                        <button 
                          onClick={() => { if(new_selected_cover) setNewSetupStep('customize') }} 
                          disabled={!new_selected_cover}
                          style={{ 
                            padding: "14px 40px", 
                            background: new_selected_cover ? "#0F172A" : "#94A3B8", 
                            color: "#FFF", 
                            border: "none", 
                            borderRadius: "6px", 
                            fontWeight: "bold", 
                            cursor: new_selected_cover ? "pointer" : "not-allowed",
                            transition: "background 0.2s"
                          }}
                        >
                          PROCEED TO CUSTOMIZATION →
                        </button>
                    </div>
                  </div>
                )}
              </div>
            )}

{new_phase === 'idle' && new_setup_step === 'customize' && new_active_template_obj && (
  <div style={{ width: "100%", maxWidth: "1200px", animation: "new_fadein 0.4s" }}>
    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: '15px' }}>
      <button onClick={() => setNewSetupStep('template')} style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #CBD5E1', cursor: 'pointer', background: '#FFFFFF', color: '#0F172A', fontWeight: 'bold', boxShadow: "0 2px 4px rgba(0,0,0,0.02)" }}>
        ← Back to Layouts
      </button>
    </div>

    <div style={{ display: "flex", gap: "30px" }}>
      {/* LEFT PANEL: PREVIEW */}
      <div style={{ flex: 1.5, maxHeight: '700px', overflowY: 'auto', background: '#FFFFFF', color: '#0F172A', padding: '40px', borderRadius: '8px', boxShadow: '0 10px 30px rgba(0,0,0,0.08)', fontFamily: new_font_family, border: "1px solid #E2E8F0" }}>
        <div style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '20px', borderBottom: "2px solid #E2E8F0", paddingBottom: "10px" }}>Sample Report Document</div>
        <p style={{ lineHeight: '1.6', marginBottom: '25px', fontSize: "14px", color: "#334155" }}>This interactive preview accurately simulates your selected data grids and visual metrics. Hover over the elements to test interactivity.</p>
        
        {/* CHARTS GRID */}
        <div style={{ display: 'grid', gridTemplateColumns: new_selected_graphs.length > 1 ? '1fr 1fr' : '1fr', gap: '20px', marginBottom: '35px' }}>
          {new_selected_graphs.map((new_gid: any) => (
            <div key={new_gid} style={{ height: '180px', borderRadius: '8px', background: new_mock_palette.bg, border: `1px solid ${new_mock_palette.grid}`, padding: '15px', display: 'flex', flexDirection: 'column' }}>
              <div style={{ fontSize: '12px', fontWeight: 'bold', color: new_mock_palette.text, marginBottom: '15px', textAlign: 'center' }}>
                {new_available_graphs.find(g => g.id === new_gid)?.name || new_gid}
              </div>
              
              {(new_gid === 'file_types') && (
                 <div className="mock-pie" style={{ width: '100px', height: '100px', borderRadius: '50%', background: `conic-gradient(${new_mock_palette.c1} 0% 40%, ${new_mock_palette.c2} 40% 75%, ${new_mock_palette.c4} 75% 90%, ${new_mock_palette.c3} 90% 100%)`, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <span style={{ color: '#FFF', fontSize: '12px', fontWeight: 'bold', textShadow: '0px 1px 3px rgba(0,0,0,0.6)' }}>40%</span>
                 </div>
              )}
              
              {(new_gid === 'timeline') && (
                 <div className="mock-line-svg" style={{ flex: 1, borderBottom: `2px solid ${new_mock_palette.grid}`, borderLeft: `2px solid ${new_mock_palette.grid}`, position: 'relative' }}>
                    <svg viewBox="0 0 100 40" preserveAspectRatio="none" style={{ width: '100%', height: '100%', overflow: 'visible' }}>
                      <path d="M0,35 L20,25 L40,30 L60,10 L80,15 L100,5 L100,40 L0,40 Z" fill={new_mock_palette.c2} opacity="0.15" />
                      <polyline className="mock-line-path" points="0,35 20,25 40,30 60,10 80,15 100,5" fill="none" stroke={new_mock_palette.c1} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                 </div>
              )}
              
              {(new_gid === 'signals' || new_gid === 'scores' || new_gid === 'integrity' || new_gid === 'parse_errors' || new_gid === 'duckdb') && (
                 <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-around', gap: '8px', borderBottom: `2px solid ${new_mock_palette.grid}` }}>
                    <div className="mock-bar" style={{ width: '20%', height: '40%', background: new_mock_palette.c3, borderRadius: '3px 3px 0 0' }} />
                    <div className="mock-bar" style={{ width: '20%', height: '70%', background: new_mock_palette.c2, borderRadius: '3px 3px 0 0' }} />
                    <div className="mock-bar" style={{ width: '20%', height: '50%', background: new_mock_palette.c4, borderRadius: '3px 3px 0 0' }} />
                    <div className="mock-bar" style={{ width: '20%', height: '90%', background: new_mock_palette.c1, borderRadius: '3px 3px 0 0' }} />
                 </div>
              )}

              {(new_gid === 'top_entities') && (
                 <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-around', borderLeft: `2px solid ${new_mock_palette.grid}` }}>
                    <div className="mock-bar-horiz" style={{ width: '90%', height: '15px', background: new_mock_palette.c1, borderRadius: '0 3px 3px 0' }} />
                    <div className="mock-bar-horiz" style={{ width: '70%', height: '15px', background: new_mock_palette.c2, borderRadius: '0 3px 3px 0' }} />
                    <div className="mock-bar-horiz" style={{ width: '80%', height: '15px', background: new_mock_palette.c3, borderRadius: '0 3px 3px 0' }} />
                    <div className="mock-bar-horiz" style={{ width: '50%', height: '15px', background: new_mock_palette.c4, borderRadius: '0 3px 3px 0' }} />
                 </div>
              )}
            </div>
          ))}
        </div>

        {/* SAMPLE TABLE */}
        <div style={{ marginBottom: '15px', fontSize: '15px', fontWeight: 'bold', color: '#0F172A' }}>Extracted Telemetry Metrics</div>
        <table className={`table-${new_table_style}`}>
          <thead>
            <tr>{['Target Entity', 'Observed Value', 'Verification'].map((new_h: any) => <th key={new_h}>{new_h}</th>)}</tr>
          </thead>
          <tbody>
            <tr title="Hover test: This is a verified system artifact.">
              <td>System Artifact ID</td>
              <td>CASE-DEMO-2026</td>
              <td style={{ color: "#10B981", fontWeight: "bold" }}>Verified</td>
            </tr>
            <tr title="Hover test: High-risk anomaly detected in lateral movement.">
              <td>Threat Concentration</td>
              <td>High-Risk Lateral Mvmt.</td>
              <td style={{ color: "#EF4444", fontWeight: "bold" }}>Flagged</td>
            </tr>
            <tr title="Hover test: Hash chain remains intact across all jumps.">
              <td>Data Continuity</td>
              <td>Hash Chain Intact</td>
              <td style={{ color: "#10B981", fontWeight: "bold" }}>Verified</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* RIGHT PANEL: CUSTOMIZATION CONTROLS */}
      <div style={{ flex: 1 }}>
        <h3 style={{ marginBottom: "15px", color: "#0F172A" }}>Style Configuration</h3>
        
        <div style={{ display: 'flex', flexDirection: "column", gap: '10px', marginBottom: '30px' }}>
          {/* TAB BUTTONS */}
          <div style={{ display: "flex", gap: "10px" }}>
            <button onClick={() => setNewCustomTab('fonts')} style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #CBD5E1', cursor: 'pointer', background: new_custom_tab === 'fonts' ? '#0284C7' : '#FFFFFF', color: new_custom_tab === 'fonts' ? '#FFF' : '#0F172A', fontWeight: 'bold' }}>Typography</button>
            <button onClick={() => setNewCustomTab('graphs')} style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #CBD5E1', cursor: 'pointer', background: new_custom_tab === 'graphs' ? '#0284C7' : '#FFFFFF', color: new_custom_tab === 'graphs' ? '#FFF' : '#0F172A', fontWeight: 'bold' }}>Visuals</button>
            <button onClick={() => setNewCustomTab('tables')} style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #CBD5E1', cursor: 'pointer', background: new_custom_tab === 'tables' ? '#0284C7' : '#FFFFFF', color: new_custom_tab === 'tables' ? '#FFF' : '#0F172A', fontWeight: 'bold' }}>Data Grids</button>
          </div>

          {/* CUSTOMIZATION OPTIONS PANEL */}
          <div style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", padding: "20px", borderRadius: "8px", display: "flex", flexDirection: "column", gap: "10px" }}>
            {/* FONTS TAB */}
            {new_custom_tab === 'fonts' && (new_active_template_obj?.fonts || []).map((new_f: any) => <button key={new_f.id} onClick={() => setNewFontStyle(new_f.id)} style={{ padding: '12px', borderRadius: '6px', border: '1px solid #CBD5E1', cursor: 'pointer', background: new_font_style === new_f.id ? '#F1F5F9' : '#FFFFFF', color: '#0F172A', fontWeight: 'bold', textAlign: "left", display: "flex", justifyContent: "space-between" }}>{new_f.name} {new_font_style === new_f.id && <span style={{ color: "#0284C7" }}>✓</span>}</button>)}
            
            {/* GRAPHS TAB */}
            {new_custom_tab === 'graphs' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                    <div style={{ fontWeight: 'bold', color: '#0F172A', fontSize: '13px', borderBottom: '1px solid #E2E8F0', paddingBottom: '5px' }}>1. Base Palette Style</div>
                    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                        {(new_active_template_obj?.graphs || []).map((new_g: any) => (
                            <button key={new_g.id} onClick={() => setNewGraphStyle(new_g.id)} style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #CBD5E1', cursor: 'pointer', background: new_graph_style === new_g.id ? '#F1F5F9' : '#FFFFFF', color: '#0F172A', fontWeight: 'bold', display: "flex", justifyContent: "space-between", alignItems: "center" }}>{new_g.name} {new_graph_style === new_g.id && <span style={{ color: "#0284C7" }}>✓</span>}</button>
                        ))}
                    </div>
                    <div style={{ fontWeight: 'bold', color: '#0F172A', fontSize: '13px', borderBottom: '1px solid #E2E8F0', paddingBottom: '5px', marginTop: '5px', display: 'flex', justifyContent: 'space-between' }}>
                        <span>2. Include Charts (Min 1, Max 5)</span>
                        <span style={{ color: "#64748B" }}>{new_selected_graphs.length} / 5</span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                        {new_available_graphs.map((new_g: any) => {
                            const new_is_sel = new_selected_graphs.includes(new_g.id);
                          

  return (
                                <div key={new_g.id} onClick={() => new_toggle_graph(new_g.id)} style={{ padding: '10px', borderRadius: '6px', border: `1px solid ${new_is_sel ? '#0284C7' : '#E2E8F0'}`, cursor: 'pointer', background: new_is_sel ? '#F0F9FF' : '#F8FAFC', color: '#0F172A', fontSize: '12px', fontWeight: 'bold', display: "flex", alignItems: "center", gap: "8px", transition: '0.1s' }}>
                                    <div style={{ width: '16px', height: '16px', borderRadius: '4px', border: '1px solid #0284C7', background: new_is_sel ? '#0284C7' : '#FFF', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                        {new_is_sel && <span style={{ color: '#FFF', fontSize: '10px' }}>✓</span>}
                                    </div>
                                    {new_g.name}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* TABLES TAB */}
            {new_custom_tab === 'tables' && (new_active_template_obj?.tables || []).map((new_tb: any) => <button key={new_tb.id} onClick={() => setNewTableStyle(new_tb.id)} style={{ padding: '12px', borderRadius: '6px', border: '1px solid #CBD5E1', cursor: 'pointer', background: new_table_style === new_tb.id ? '#F1F5F9' : '#FFFFFF', color: '#0F172A', fontWeight: 'bold', textAlign: "left", display: "flex", justifyContent: "space-between" }}>{new_tb.name} {new_table_style === new_tb.id && <span style={{ color: "#0284C7" }}>✓</span>}</button>)}
          </div>
        </div>

      </div>
    </div>
  </div>
)}
        </div>
      </DialogContent>
    </Dialog>
  );
}
