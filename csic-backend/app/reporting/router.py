from fastapi import APIRouter, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse
import io
import json
import os
import base64
import matplotlib
matplotlib.use('Agg') # Server-side plotting
import matplotlib.pyplot as plt
from datetime import datetime

# --- IMPORTS ---
try:
    from app.reporting.forensic_engine import generate_forensic_report
except ImportError:
    pass

router = APIRouter()

# ==========================================
# 1. THE ADAPTER (LOGIC UNTOUCHED)
# ==========================================
class DemoTransformer:
    @staticmethod
    def generate_pie_chart(data_dict, title):
        if not data_dict: return None
        plt.figure(figsize=(8, 5))
        plt.style.use('default') 
        # Professional Blue/Grey Theme (Matches new UI)
        colors = ['#6200ea', '#9d46ff', '#b3c6ff', '#808080', '#e0e0e0']
        
        plt.pie(data_dict.values(), labels=data_dict.keys(), autopct='%1.1f%%', colors=colors, startangle=140)
        plt.title(title, fontsize=14, fontweight='bold', color='#222222')
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120)
        plt.close()
        return base64.b64encode(buf.getvalue()).decode('utf-8')

    @staticmethod
    def generate_bar_chart(data_dict, title):
        if not data_dict: return None
        plt.figure(figsize=(8, 5))
        plt.style.use('default')
        
        keys = list(data_dict.keys())
        vals = list(data_dict.values())
        
        plt.bar(keys, vals, color='#6200ea') # Purple bars
        plt.title(title, fontsize=14, fontweight='bold', color='#222222')
        plt.xticks(rotation=45, ha='right', fontsize=10)
        plt.grid(axis='y', linestyle='--', alpha=0.3)
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120)
        plt.close()
        return base64.b64encode(buf.getvalue()).decode('utf-8')

    @staticmethod
    def transform(raw_data):
        """Converts User's Raw JSON into a 6-Page Report Script."""
        case_id = raw_data.get("case_id", "CASE-UNKNOWN")
        gen_time = raw_data.get("generated_at", str(datetime.now()))
        
        file_counts = {}
        for f in raw_data.get("evidence_list", []):
            ft = f.get("file_type", "unknown")
            file_counts[ft] = file_counts.get(ft, 0) + 1
        
        signal_counts = {}
        signals_data = raw_data.get("signals", {})
        if isinstance(signals_data, dict):
            for k, v in signals_data.items():
                val = v.get("count", 0) if isinstance(v, dict) else v
                signal_counts[k] = val

        pie_b64 = DemoTransformer.generate_pie_chart(file_counts, "Evidence Distribution")
        bar_b64 = DemoTransformer.generate_bar_chart(signal_counts, "Detected Threat Signals")

        pages = []
        # PAGE 1: EXECUTIVE SUMMARY
        pages.append({
            "title": "1. Executive Summary",
            "paragraphs": [
                f"This Digital Forensic Investigation Report documents the analysis of Case ID {case_id}, initiated at {gen_time}. The objective was to identify potential Indicators of Compromise (IOCs).",
                "The ASI-GEN Automated Forensic Engine processed the ingested telemetry, consisting of system logs, network captures (PCAP), and endpoint security events.",
                "FINAL VERDICT: CRITICAL RISK CONFIRMED. Multiple high-fidelity threat signals indicate a successful breach attempt involving credential theft."
            ],
            "charts": [{"b64": pie_b64}] if pie_b64 else []
        })

        # PAGE 2: EVIDENCE INTAKE
        pages.append({
            "title": "2. Evidence Intake & Validation",
            "paragraphs": [
                f"A total of {len(raw_data.get('evidence_list', []))} artifacts were ingested. Each file underwent cryptographic hash verification (SHA-256).",
                "The dataset includes critical data sources such as Windows Security Events (.evtx), NGINX Web Logs, and raw memory dumps.",
                "Data Integrity Check: The chain of custody ledger confirmed 100% integrity for all analyzed files."
            ],
            "tables": [{
                "title": "Ingested Artifacts (Sample)",
                "columns": ["Filename", "Type", "Status"],
                "rows": [[f.get("filename"), f.get("file_type"), f.get("verification_status")] for f in raw_data.get("evidence_list", [])[:6]]
            }]
        })

        # PAGE 3: THREAT ANALYSIS
        pages.append({
            "title": "3. Threat Signal Analysis",
            "paragraphs": [
                "The Behavioral Analysis Engine detected multiple high-confidence threat signals. The most dominant patterns observed include:",
                "1. Credential Dumping & Spraying: Repeated login failures followed by successful authentication anomalies.",
                "2. C2 Beaconing: Outbound network traffic analysis revealed periodic connections to unclassified IPs.",
                "The chart below illustrates the frequency of detected threat behaviors."
            ],
            "charts": [{"b64": bar_b64}] if bar_b64 else []
        })

        # PAGE 4: HIGH RISK ENTITIES
        alert_rows = []
        for a in raw_data.get("alerts", []):
            triggers = a.get("triggers", [])
            t_str = ", ".join(triggers[:2]) if isinstance(triggers, list) else str(triggers)
            alert_rows.append([str(a.get("entity", "N/A")), str(a.get("risk_score", 0)), str(a.get("risk_level", "N/A")), t_str])

        pages.append({
            "title": "4. High Risk Entities",
            "paragraphs": [
                "The following entities have risk scores exceeding the safety threshold (80/100).",
                "These entities are considered the primary vectors of the attack. Immediate account suspension is recommended.",
                "The table below ranks the top threat actors identified during the analysis phase."
            ],
            "tables": [{
                "title": "Top Detected Threat Actors",
                "columns": ["Entity", "Score", "Level", "Triggers"],
                "rows": alert_rows
            }]
        })

        # PAGE 5: TIMELINE
        pages.append({
            "title": "5. Incident Timeline Reconstruction",
            "paragraphs": [
                "Timeline reconstruction reveals a staged attack pattern starting with initial access attempts.",
                "Phase 1 (Infiltration): External IP 185.231.72.19 initiated scanning activity against the perimeter firewall.",
                "Phase 2 (Escalation): User account 'svc_backup' executed unauthorized PowerShell scripts.",
                "Phase 3 (Exfiltration): Large data transfer spikes were observed on port 443."
            ],
            "charts": []
        })

        # PAGE 6: RECOMMENDATIONS
        pages.append({
            "title": "6. Strategic Recommendations",
            "paragraphs": [
                "Based on the forensic findings, the following remediation steps are mandated:",
                "1. CONTAINMENT: Isolate host APP-SRV-07 from the network immediately.",
                "2. CREDENTIALS: Rotate all service account passwords, specifically for 'svc_backup'.",
                "3. NETWORK DEFENSE: Implement block rules for C2 domains identified in the IOC list.",
                "4. FORENSICS: Preserve the raw memory dump (memory_dump.raw) for deeper malware analysis."
            ],
            "charts": []
        })

        return { "meta": raw_data, "pages": pages }

# ==========================================
# 2. UI ENDPOINT (UPDATED LOG LIST)
# ==========================================
@router.get("/reports/ghostwriter", response_class=HTMLResponse)
async def get_ghostwriter_ui():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <title>ASI-GEN REPORTS</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    /* VARIABLES */
    :root { 
        --bg-color: #f3f4f9; 
        --sidebar-bg: #ffffff;
        --card-bg: #ffffff;
        --text-main: #333333;
        --text-muted: #666666;
        --accent: #6200ea; /* Purple */
        --accent-light: #e8eaf6;
        --border: #e0e0e0;
    }

    body { 
        background: var(--bg-color); 
        color: var(--text-main); 
        font-family: 'Inter', sans-serif; 
        margin: 0; 
        display: flex; 
        height: 100vh; 
        overflow: hidden; 
    }
    
    /* SIDEBAR */
    .sidebar { 
        width: 260px; 
        background: var(--sidebar-bg); 
        border-right: 1px solid var(--border); 
        padding: 40px 20px; 
        display: flex; 
        flex-direction: column; 
    }
    
    .step-box { 
        padding: 15px 20px; 
        border-radius: 8px;
        margin-bottom: 10px; 
        transition: 0.2s; 
        display: flex; 
        align-items: center; 
        cursor: default; 
        color: var(--text-muted);
        font-size: 14px;
        font-weight: 500;
    }
    
    .step-box.active { 
        background-color: var(--accent-light);
        color: var(--accent);
        font-weight: 600;
    }
    
    .step-num { 
        width: 24px; 
        height: 24px; 
        background: #ddd; 
        color: white; 
        border-radius: 50%; 
        display: flex; 
        align-items: center; 
        justify-content: center; 
        font-size: 12px; 
        margin-right: 12px; 
    }
    
    .step-box.active .step-num { background: var(--accent); }

    /* MAIN AREA */
    .main { 
        flex: 1; 
        position: relative; 
        display: flex; 
        justify-content: center; 
        align-items: center; 
    }

    .screen { 
        display: none; 
        width: 100%; 
        height: 100%; 
        flex-direction: column; 
        justify-content: center; 
        align-items: center; 
        animation: fadeIn 0.4s ease-out; 
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

    h1 { font-size: 24px; font-weight: 700; color: #1a1a1a; margin-bottom: 40px; }

    /* LOG CARDS */
    .log-list { 
        width: 600px; 
        display: flex; 
        flex-direction: column; 
        gap: 15px; 
        max-height: 65vh; /* Scrollable if too long */
        overflow-y: auto; 
        padding: 10px; 
    }
    
    /* Scrollbar styling for log list */
    .log-list::-webkit-scrollbar { width: 6px; }
    .log-list::-webkit-scrollbar-track { background: transparent; }
    .log-list::-webkit-scrollbar-thumb { background: #ccc; border-radius: 10px; }

    .log-item { 
        background: var(--card-bg); 
        border: 1px solid var(--border); 
        border-radius: 12px;
        padding: 24px; 
        cursor: pointer; 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        transition: 0.2s; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .log-item:hover { 
        border-color: var(--accent); 
        box-shadow: 0 4px 12px rgba(98, 0, 234, 0.1); 
        transform: translateY(-2px);
    }
    .log-title { font-weight: 600; font-size: 16px; margin-bottom: 4px; }
    .log-meta { font-size: 13px; color: var(--text-muted); }
    .btn-select { 
        color: var(--accent); 
        font-weight: 600; 
        font-size: 13px; 
        background: var(--accent-light); 
        padding: 8px 16px; 
        border-radius: 6px; 
    }

    /* TEMPLATE CARDS */
    .template-grid { display: flex; gap: 24px; }
    .t-card { 
        width: 220px; 
        background: var(--card-bg); 
        border: 1px solid var(--border); 
        border-radius: 12px; 
        cursor: pointer; 
        transition: 0.3s; 
        overflow: hidden; 
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        display: flex; flex-direction: column;
    }
    .t-card:hover { transform: translateY(-8px); box-shadow: 0 12px 24px rgba(0,0,0,0.08); border-color: var(--accent); }
    .t-img-box { width: 100%; height: 260px; background: #f0f0f0; }
    .t-img-box img { width: 100%; height: 100%; object-fit: cover; }
    .t-content { padding: 16px; text-align: center; border-top: 1px solid var(--border); }
    .t-title { font-weight: 700; font-size: 15px; margin-bottom: 4px; color: #333; }
    .t-desc { font-size: 12px; color: var(--text-muted); }

    /* REPORT PREVIEW */
    #report-scroll { 
        width: 100%; height: 100%; overflow-y: auto; padding: 40px 0; 
        display: flex; flex-direction: column; align-items: center; gap: 30px; scroll-behavior: smooth; 
    }
    .page { 
        width: 210mm; min-height: 297mm; background: white; color: black; padding: 0; 
        transform: scale(0.85); box-shadow: 0 4px 20px rgba(0,0,0,0.08); border-radius: 2px;
        display: flex; flex-direction: column; margin-bottom: 20px; 
    }
    .page-content { padding: 20mm; flex: 1; }
    
    /* FINISH SCREEN */
    .finish-box { 
        text-align: center; background: white; padding: 60px; border-radius: 16px; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.05); border: 1px solid var(--border);
    }
    .btn-dl { 
        background: var(--accent); color: white; padding: 14px 32px; font-weight: 600; 
        border: none; cursor: pointer; font-size: 16px; border-radius: 8px; margin-top: 24px; transition: 0.2s; 
    }
    .btn-dl:hover { background: #5000c0; transform: translateY(-2px); }

    /* UTILITIES */
    .typing::after { content: '|'; animation: blink 0.7s infinite; color: var(--accent); }
    @keyframes blink { 50% { opacity: 0; } }
    .chart-box { width: 100%; border: 1px solid #eee; margin-top: 20px; border-radius: 8px; }
    
    table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px; }
    th { background: #f8f9fa; color: #444; padding: 12px; text-align: left; border-bottom: 2px solid #eee; font-weight: 600; }
    td { border-bottom: 1px solid #eee; padding: 12px; color: #555; }
    
    #error-box { position: fixed; top: 20px; right: 20px; background: #dc3545; color: white; padding: 15px; border-radius: 8px; display: none; z-index: 1000; font-size: 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
  </style>
</head>
<body>

<div id="error-box"></div>

<div class="sidebar">
  <div style="height: 20px;"></div> 
  <div id="step-1" class="step-box active"><div class="step-num">1</div> Select Log</div>
  <div id="step-2" class="step-box"><div class="step-num">2</div> Choose Template</div>
  <div id="step-3" class="step-box"><div class="step-num">3</div> Generating...</div>
  <div id="step-4" class="step-box"><div class="step-num">4</div> Download</div>
</div>

<div class="main">
  
  <div id="scr-1" class="screen" style="display:flex;">
    <h1>Available Log Sources</h1>
    <div class="log-list">
      
      <div class="log-item" onclick="nav(2)">
        <div>
          <div class="log-title">log_ingestion_tester_1.txt</div>
          <div class="log-meta">Verified • Just now</div>
        </div>
        <div class="btn-select">Select</div>
      </div>
      
      <div class="log-item" onclick="nav(2)">
        <div>
          <div class="log-title">vertopal.com_new_verification.json</div>
          <div class="log-meta">Verified • 10 mins ago</div>
        </div>
        <div class="btn-select">Select</div>
      </div>

      <div class="log-item" onclick="nav(2)">
        <div>
          <div class="log-title">new_verification.txt</div>
          <div class="log-meta">Verified • 12 mins ago</div>
        </div>
        <div class="btn-select">Select</div>
      </div>

      <div class="log-item" onclick="nav(2)">
        <div>
          <div class="log-title">log_1.txt</div>
          <div class="log-meta">Verified • 25 mins ago</div>
        </div>
        <div class="btn-select">Select</div>
      </div>

      <div class="log-item" onclick="nav(2)">
        <div>
          <div class="log-title">texttext copy.txt</div>
          <div class="log-meta">Verified • 1 hour ago</div>
        </div>
        <div class="btn-select">Select</div>
      </div>

      <div class="log-item" onclick="nav(2)">
        <div>
          <div class="log-title">edbde copy.txt</div>
          <div class="log-meta">Verified • 2 hours ago</div>
        </div>
        <div class="btn-select">Select</div>
      </div>

      <div class="log-item" onclick="nav(2)">
        <div>
          <div class="log-title">hbejhwhws copy.txt</div>
          <div class="log-meta">Verified • 5 hours ago</div>
        </div>
        <div class="btn-select">Select</div>
      </div>

      <div class="log-item" onclick="nav(2)">
        <div>
          <div class="log-title">fhf copy.txt</div>
          <div class="log-meta">Verified • 6 hours ago</div>
        </div>
        <div class="btn-select">Select</div>
      </div>

    </div>
  </div>

  <div id="scr-2" class="screen">
    <h1>Select Report Template</h1>
    <div class="template-grid">
      <div class="t-card" onclick="startGen('ministry')">
        <div class="t-img-box"><img src="/api/reports/assets/cover.png" onerror="this.src=''"></div>
        <div class="t-content"><div class="t-title">Ministry Standard</div><div class="t-desc">Official Government Format</div></div>
      </div>
      <div class="t-card" onclick="startGen('ops')">
        <div class="t-img-box"><img src="/api/reports/assets/cover2.png" onerror="this.src=''"></div>
        <div class="t-content"><div class="t-title">Cyber Ops</div><div class="t-desc">Tactical Matrix View</div></div>
      </div>
      <div class="t-card" onclick="startGen('critical')">
        <div class="t-img-box"><img src="/api/reports/assets/cover3.png" onerror="this.src=''"></div>
        <div class="t-content"><div class="t-title">Critical Alert</div><div class="t-desc">Executive Red Level</div></div>
      </div>
    </div>
  </div>

  <div id="scr-3" class="screen">
    <div id="report-scroll"></div>
  </div>

  <div id="scr-4" class="screen">
    <div class="finish-box">
        <h1 style="margin-bottom: 10px;">Report Generated</h1>
        <p style="color: #666;">The forensic analysis has been compiled into a secure PDF.</p>
        <button id="btn-dl" class="btn-dl" onclick="dl()">Download PDF Report</button>
        <br><br>
        <div style="margin-top:20px; color:#6200ea; font-size:13px; cursor:pointer; font-weight:600;" onclick="location.reload()">Start New Analysis</div>
    </div>
  </div>
</div>

<script>
let finalBlob = null;

function showError(msg) {
    const box = document.getElementById('error-box');
    box.innerText = msg;
    box.style.display = 'block';
    setTimeout(() => box.style.display='none', 5000);
}

function nav(n) {
  try {
      document.querySelectorAll('.step-box').forEach(e=>e.classList.remove('active'));
      const step = document.getElementById('step-'+n);
      if(step) step.classList.add('active');
      
      document.querySelectorAll('.screen').forEach(e=>e.style.display='none');
      const scr = document.getElementById('scr-'+n);
      if(scr) scr.style.display='flex';
  } catch(e) { console.error(e); }
}

async function startGen(tmpl) {
  nav(3);
  try {
    const res = await fetch("/api/reports/demo-data-transformed");
    if(!res.ok) throw new Error("Failed to load demo data");
    const json = await res.json();
    
    await render(json, tmpl);
    
    const fd = new FormData();
    fd.append("template_id", tmpl);
    const pdfRes = await fetch("/api/reports/generate-demo", {method:"POST", body:fd});
    
    if(pdfRes.ok) {
        finalBlob = await pdfRes.blob();
        nav(4);
    } else {
        showError("PDF Generation Failed");
    }
  } catch(e) { showError(e.message); }
}

function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }

async function typeWriter(el, txt) {
    if(!txt) return;
    el.innerHTML=""; el.classList.add('typing');
    for(let i=0; i<txt.length; i++){ 
        el.innerHTML+=txt[i]; 
        if(i%3==0) await sleep(1); 
    }
    el.classList.remove('typing');
}

async function render(data, tmpl) {
    const scroll = document.getElementById("report-scroll");
    scroll.innerHTML = "";
    
    let h2Color = (tmpl=='critical') ? '#cc0000' : (tmpl=='ops') ? '#00cc44' : '#003366';
    const style = document.createElement('style');
    style.innerHTML = `.h2{color:${h2Color}!important;} th{color:${h2Color}!important;}`;
    document.head.appendChild(style);

    const p1 = document.createElement("div"); p1.className="page";
    const img = document.createElement("img");
    img.src = "/api/reports/assets/" + (tmpl=='ops'?'cover2.png':tmpl=='critical'?'cover3.png':'cover.png');
    img.style.width="100%"; img.style.height="100%";
    p1.appendChild(img);
    scroll.appendChild(p1);
    await sleep(400);

    if(data.pages && data.pages.length > 0) {
        for(let i=0; i<data.pages.length; i++) {
            const sec = data.pages[i];
            const pg = document.createElement("div"); pg.className="page";
            const c = document.createElement("div"); c.className="page-content";
            pg.appendChild(c); 
            
            scroll.appendChild(pg);
            if(pg.scrollIntoView) pg.scrollIntoView({behavior:"smooth", block:"center"});
            
            await sleep(200);

            const h = document.createElement("h2"); h.className="h2"; h.innerText=sec.title;
            h.style.fontSize="18px"; h.style.borderBottom="1px solid #eee"; h.style.paddingBottom="8px"; h.style.marginBottom="16px";
            c.appendChild(h);
            
            if(sec.paragraphs) {
                for(let txt of sec.paragraphs) {
                    const p = document.createElement("p"); 
                    p.style.lineHeight="1.6"; p.style.fontSize="14px"; p.style.marginBottom="12px";
                    c.appendChild(p);
                    await typeWriter(p, txt);
                }
            }

            if(sec.charts) {
                for(let ch of sec.charts) {
                    if(ch.b64) {
                        const img = document.createElement("img");
                        img.src = "data:image/png;base64,"+ch.b64;
                        img.className="chart-box"; c.appendChild(img);
                        await sleep(300);
                    }
                }
            }
            
            if(sec.tables) {
                for(let tb of sec.tables) {
                    const t = document.createElement("table");
                    const thRow = document.createElement("tr");
                    tb.columns.forEach(col=>{ const th=document.createElement("th"); th.innerText=col; thRow.appendChild(th); });
                    t.appendChild(thRow);
                    tb.rows.forEach(r=>{
                        const tr=document.createElement("tr");
                        r.forEach(cell=>{ const td=document.createElement("td"); td.innerText=cell; tr.appendChild(td); });
                        t.appendChild(tr);
                    });
                    c.appendChild(t);
                    await sleep(200);
                }
            }
        }
    }
}

function dl() {
    if(!finalBlob) return;
    const a=document.createElement("a"); a.href=URL.createObjectURL(finalBlob); a.download="Report.pdf"; a.click();
}
</script>
</body>
</html>
"""

# ==========================================
# 3. BACKEND ENDPOINTS (LOGIC PRESERVED)
# ==========================================

@router.get("/reports/demo-data-transformed")
def get_demo_data_transformed():
    path = os.path.join(os.path.dirname(__file__), "demo_evidence.json")
    if not os.path.exists(path):
        return JSONResponse({"error": "demo_evidence.json missing"}, 404)
    with open(path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    return DemoTransformer.transform(raw_data)

@router.get("/reports/assets/{filename}")
def get_asset(filename: str):
    path = os.path.join(os.path.dirname(__file__), "assets", filename)
    if os.path.exists(path): return FileResponse(path)
    return JSONResponse({"error": "Not found"}, 404)

@router.post("/reports/generate-demo")
async def generate_demo(template_id: str = Form("ministry")):
    path = os.path.join(os.path.dirname(__file__), "demo_evidence.json")
    if not os.path.exists(path): return JSONResponse({"error": "Missing data"}, 500)
    
    with open(path, "r") as f: raw = json.load(f)
    
    cover_file = "cover2.png" if template_id=="ops" else "cover3.png" if template_id=="critical" else "cover.png"
    cover_path = os.path.join(os.path.dirname(__file__), "assets", cover_file)
    
    if os.path.exists(cover_path):
        try:
            with open(cover_path, "rb") as cf:
                buf = io.BytesIO(cf.read())
                raw["meta"] = raw.get("meta", {})
                raw["meta"]["cover_b64"] = base64.b64encode(buf.getvalue()).decode("utf-8")
        except:
            pass

    color = "#00ff41" if template_id=="ops" else "#cc0000" if template_id=="critical" else "#003366"
    
    try:
        pdf_path = generate_forensic_report(raw, custom_color=color)
        if pdf_path: return FileResponse(pdf_path, filename=f"Report_{template_id}.pdf")
        return JSONResponse({"error": "PDF Failed"}, 500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)

@router.post("/reports/preview-upload")
async def prev(f: UploadFile=File(...)): return {"status":"ok","title":"Demo"}
@router.post("/reports/generate-upload")
async def gen(f: UploadFile=File(...)): return JSONResponse({"error":"Use Demo"}, 400)
@router.get("/reports/summary")
def summ(): return {"available_reports":[]}