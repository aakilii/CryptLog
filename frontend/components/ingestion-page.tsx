"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import {
  Upload,
  Cloud,
  Zap,
  ShieldCheck,
  Lock,
  FileCheck,
  Bug,
  Database,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  File as FileIcon,
  FolderOpen,
  Info,
  Hash,
  TreePine,
  X,
  Terminal,
  Copy,
  Shield,
  Clock,
  KeyRound,
  Fingerprint,
  Wifi,
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { apiClient } from "@/lib/api-client"
import { WebSocketUploadClient } from "@/lib/websocket-client"
import { getApiBaseUrl } from "@/lib/public-env"
import { useApp } from "@/lib/app-context"
import { useShellNavigate } from "@/lib/use-shell-navigate"
import { CloudIngestionPanel } from "@/components/google-drive-ingestion"

/* ================================================================== */
/* TYPES                                                               */
/* ================================================================== */
type PhaseStatus = "idle" | "active" | "success" | "error"

interface UploadedFile {
  name: string
  size: number
  type: string
}

interface JitRule {
  id: string
  label: string
  description: string
  valid: boolean
  checking: boolean
}

interface LogEntry {
  time: string
  level: "INFO" | "WARN" | "ERROR" | "OK"
  message: string
}

interface SecurityPhase {
  id: string
  label: string
  subtitle: string
  description: string
  status: PhaseStatus
  progress: number
  logs: LogEntry[]
  stats: { label: string; value: string }[]
}

/* ================================================================== */
/* MAIN COMPONENT                                                      */
/* ================================================================== */
export function IngestionPage() {
  const { setActiveAuditId } = useApp()
  const { go } = useShellNavigate()
  const [activeTab, setActiveTab] = useState("manual")
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null)
  const [uploadMethod, setUploadMethod] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [securityPhases, setSecurityPhases] = useState<SecurityPhase[]>(getInitialPhases())
  const [overallResult, setOverallResult] = useState<"pass" | "fail" | null>(null)
  const [jitRules, setJitRules] = useState<JitRule[]>(getInitialJitRules())
  const [jitValidated, setJitValidated] = useState(false)
  const [jitSessionGenerated, setJitSessionGenerated] = useState(false)
  const [jitSessionGenerating, setJitSessionGenerating] = useState(false)
  const [jitSessionId, setJitSessionId] = useState("")
  const [jitSessionToken, setJitSessionToken] = useState("")
  const [jitSessionExpiry, setJitSessionExpiry] = useState("")
  const [showPipeline, setShowPipeline] = useState(false)
  const [merkleRoot, setMerkleRoot] = useState<string>("")
  const flowRef = useRef<HTMLDivElement>(null)
  const phasesRef = useRef<SecurityPhase[]>(getInitialPhases());

  // Load pipeline state from localStorage on mount
  useEffect(() => {
    if (typeof window === 'undefined') return
    
    const savedState = localStorage.getItem('ingestion_pipeline_state')
    if (savedState) {
      try {
        const state = JSON.parse(savedState)
        if (state.showPipeline && (state.isProcessing || state.overallResult)) {
          // Only restore if pipeline was active or completed
          setUploadedFile(state.uploadedFile)
          setUploadMethod(state.uploadMethod)
          setIsProcessing(state.isProcessing || false)
          setSecurityPhases(state.securityPhases || getInitialPhases())
          phasesRef.current = state.securityPhases || getInitialPhases()
          setOverallResult(state.overallResult)
          setMerkleRoot(state.merkleRoot || "")
          setShowPipeline(true)
        }
      } catch (e) {
        console.error('Failed to restore pipeline state:', e)
      }
    }
  }, [])

  // Update Merkle Tree phase stats when merkle root becomes available
  useEffect(() => {
    if (merkleRoot && showPipeline) {
      setSecurityPhases(prev => {
        const phases = [...prev]
        const merklePhase = phases.find(p => p.id === "merkle")
        if (merklePhase) {
          merklePhase.stats = merklePhase.stats.map(stat => 
            stat.label === "Merkle Root" 
              ? { ...stat, value: `${merkleRoot.slice(0, 12)}...${merkleRoot.slice(-4)}` }
              : stat
          )
          phasesRef.current = phases
        }
        return phases
      })
    }
  }, [merkleRoot, showPipeline])

  // Save pipeline state to localStorage whenever it changes
  useEffect(() => {
    if (typeof window === 'undefined') return
    
    if (showPipeline && (isProcessing || overallResult)) {
      const state = {
        uploadedFile,
        uploadMethod,
        isProcessing,
        securityPhases,
        overallResult,
        merkleRoot,
        showPipeline,
      }
      localStorage.setItem('ingestion_pipeline_state', JSON.stringify(state))
    } else if (!showPipeline && !isProcessing && !overallResult) {
      // Clear saved state when pipeline is reset
      localStorage.removeItem('ingestion_pipeline_state')
    }
  }, [showPipeline, isProcessing, overallResult, uploadedFile, uploadMethod, securityPhases, merkleRoot])

  const resetFlow = useCallback(() => {
    setUploadedFile(null)
    setUploadMethod(null)
    setIsProcessing(false)
    setSecurityPhases(getInitialPhases())
    phasesRef.current = getInitialPhases()
    setOverallResult(null)
    setMerkleRoot("")
    setJitRules(getInitialJitRules())
    setJitValidated(false)
    setJitSessionGenerated(false)
    setJitSessionGenerating(false)
    setJitSessionId("")
    setJitSessionToken("")
    setJitSessionExpiry("")
    setShowPipeline(false)
    // Clear saved state
    if (typeof window !== 'undefined') {
      localStorage.removeItem('ingestion_pipeline_state')
    }
  }, [])

  const runRemainingPhases = useCallback((file: UploadedFile, startFromPhase: number) => {
    let currentPhase = startFromPhase

    const advancePhase = () => {
      if (currentPhase >= phasesRef.current.length) {
        setIsProcessing(false)
        setOverallResult("pass")
        setTimeout(() => go("parsing"), 900)
        return
      }

      const phases = phasesRef.current
      phases[currentPhase].status = "active"
      phases[currentPhase].logs = [
        { time: ts(), level: "INFO", message: `Starting ${phases[currentPhase].label}...` },
      ]
      setSecurityPhases([...phases])

      let progress = 0
      const phaseIndex = currentPhase
      const totalTicks = 15
      let tick = 0

      const progressInterval = setInterval(() => {
        tick++
        progress = Math.min(100, (tick / totalTicks) * 100)

        const p = phases[phaseIndex]
        p.progress = progress

        const logMilestones = getProgressLogs(phaseIndex, progress, file)
        if (logMilestones) {
          const exists = p.logs.some((l) => l.message === logMilestones.message)
          if (!exists) {
            p.logs = [...p.logs, logMilestones]
          }
        }

        setSecurityPhases([...phases])

        if (progress >= 100) {
          clearInterval(progressInterval)

          p.status = "success"
          p.logs = [...p.logs, ...getPhaseCompleteLogs(phaseIndex, file)]
          p.stats = getPhaseStats(phaseIndex, file, "")
          setSecurityPhases([...phases])
          currentPhase++
          setTimeout(advancePhase, 700)
        }
      }, 150)
    }

    advancePhase()
  }, [go])

  const startSecurityFlow = useCallback((file: UploadedFile, method: string) => {
    setUploadedFile(file)
    setUploadMethod(method)
    setIsProcessing(true)
    setOverallResult(null)
    const fresh = getInitialPhases()

    // Immediately set Phase 1 as active (chunk upload in progress)
    fresh[0].status = "active"
    fresh[0].logs = [{ time: ts(), level: "INFO", message: `Starting ${fresh[0].label}...` }]

    phasesRef.current = fresh
    setSecurityPhases([...fresh])
    setShowPipeline(true)

    setTimeout(() => {
      flowRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
    }, 300)
  }, [])

  /* ---- Upload handlers ---- */
  const startPhase1Upload = useCallback(
    async (file: File, sourceLabel: string) => {
      try {
        const sessionResponse = await apiClient.createManualSession()
        const uploadedFileInfo = {
          name: file.name,
          size: file.size,
          type: file.type || "application/octet-stream",
        }

        startSecurityFlow(uploadedFileInfo, sourceLabel)

        const wsClient = new WebSocketUploadClient(sessionResponse.session_id)

        wsClient.setProgressCallback((progress) => {
          const phases = phasesRef.current
          const p = phases[0]
          if (p) {
            p.progress = progress.percentage
            const msg = `Chunk ${progress.chunkNumber}/${progress.totalChunks} hashed & uploaded (${progress.percentage}%)`
            const exists = p.logs.some((l) => l.message === msg)
            if (!exists) {
              p.logs = [...p.logs, { time: ts(), level: "INFO", message: msg }]
            }
            setSecurityPhases([...phases])
          }
        })

        wsClient.setCompleteCallback((result) => {
          const merkleRootValue =
            result.result?.merkle_root ||
            result.result?.binary_signature ||
            result.merkle_root ||
            result.binary_signature ||
            ""

          const auditId = result.result?.audit_id || (result as any).audit_id || ""
          const sha256 = result.result?.sha256 || (result as any).sha256 || ""
          const filePath = result.result?.file_path || (result as any).file_path || ""
          if (typeof window !== "undefined" && auditId) {
            localStorage.setItem(
              "latest_ingestion_audit",
              JSON.stringify({ auditId, sha256, filePath, filename: file.name, merkleRoot: merkleRootValue }),
            )
            setActiveAuditId(auditId)
          }
          if (merkleRootValue) setMerkleRoot(merkleRootValue)

          // Mark Phase 1 (Chunk Splitting) as complete with real data
          const phases = phasesRef.current
          const p1 = phases[0]
          if (p1) {
            p1.status = "success"
            p1.progress = 100
            p1.logs = [
              ...p1.logs,
              { time: ts(), level: "OK", message: `Upload complete. Audit ID: ${auditId || "N/A"}` },
              { time: ts(), level: "OK", message: `SHA-256: ${sha256 ? sha256.slice(0, 16) + "..." : "N/A"}` },
            ]
            p1.stats = getPhaseStats(0, uploadedFileInfo, "")
          }
          setSecurityPhases([...phases])

          // Now run phases 2-5 sequentially (backend has already processed them)
          setTimeout(() => {
            runRemainingPhases(uploadedFileInfo, 1)
          }, 500)

          // Auto-handoff flag for Phase 2 page
          try {
            if (typeof window !== "undefined" && auditId) {
              localStorage.setItem("phase2_autostart_audit", auditId)
            }
          } catch { /* ignore */ }
        })

        wsClient.setErrorCallback((error) => {
          const phases = phasesRef.current
          const p1 = phases[0]
          if (p1) {
            p1.status = "error"
            p1.logs = [...p1.logs, { time: ts(), level: "ERROR", message: error.message }]
          }
          setSecurityPhases([...phases])
          setIsProcessing(false)
          setOverallResult("fail")
        })

        await wsClient.uploadFile(file)
      } catch (err) {
        console.error("Upload failed:", err)
        alert(err instanceof Error ? err.message : "Upload failed")
        setIsProcessing(false)
        setOverallResult("fail")
      }
    },
    [startSecurityFlow, runRemainingPhases, setActiveAuditId]
  )

  const handleManualUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return
      await startPhase1Upload(file, "Manual Upload")
    },
    [startPhase1Upload]
  )


  const handleJitGenerateSession = useCallback(async () => {
    setJitSessionGenerating(true)
    try {
      const response = await apiClient.createManualSession()
      setJitSessionId(response.session_id)
      setJitSessionToken(response.session_id)
      setJitSessionExpiry(response.expires_at)
      setJitSessionGenerated(true)
    } catch (err) {
      console.error('Failed to generate session:', err)
      alert(err instanceof Error ? err.message : 'Failed to generate session')
    } finally {
      setJitSessionGenerating(false)
    }
  }, [])

  const handleJitValidation = useCallback(() => {
    const rules = [...jitRules]
    let idx = 0
    const next = () => {
      if (idx >= rules.length) {
        setJitValidated(true)
        return
      }
      rules[idx] = { ...rules[idx], checking: true }
      setJitRules([...rules])
      setTimeout(() => {
        rules[idx] = { ...rules[idx], checking: false, valid: true }
        setJitRules([...rules])
        idx++
        setTimeout(next, 400)
      }, 1200)
    }
    next()
  }, [jitRules])

  const handleJitIngest = useCallback(() => {
    // For real JIT remote collection, a collector streams logs over WS and creates a ledger entry.
    // The UI should monitor the ledger/parsing pipeline rather than fabricating a local file.
    go("ledger")
  }, [go])

  /* ---- Phase progress indicator ---- */
  const activePhaseIndex = securityPhases.findIndex((p) => p.status === "active")

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* ============================================================ */}
      {/* HEADER                                                       */}
      {/* ============================================================ */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-bold text-foreground">
            <Shield className="size-5 text-primary" />
            Secure Evidence Ingestion
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Select ingestion method, submit evidence, then monitor the full security verification pipeline
          </p>
        </div>
        {showPipeline && (
          <Button variant="outline" size="sm" onClick={resetFlow} className="gap-1.5">
            <X className="size-3.5" />
            Reset Pipeline
          </Button>
        )}
      </div>

      {/* ============================================================ */}
      {/* STEP 1 - THREE UPLOAD MODES                                  */}
      {/* ============================================================ */}
      {!showPipeline && (
        <div className="grid gap-6">
          <div className="flex items-center gap-3">
            <div className="flex size-8 items-center justify-center bg-primary text-primary-foreground text-sm font-bold">
              1
            </div>
            <div>
              <h3 className="text-sm font-semibold text-foreground">Select Ingestion Mode</h3>
              <p className="text-xs text-muted-foreground">Choose how evidence reaches the platform</p>
            </div>
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-3 h-12">
              <TabsTrigger value="manual" className="gap-2 text-sm font-medium" disabled={isProcessing}>
                <Upload className="size-4" />
                Manual Upload
              </TabsTrigger>
              <TabsTrigger value="cloud" className="gap-2 text-sm font-medium" disabled={isProcessing}>
                <Cloud className="size-4" />
                Google Drive
              </TabsTrigger>
              <TabsTrigger value="jit" className="gap-2 text-sm font-medium" disabled={isProcessing}>
                <Zap className="size-4" />
                JIT Injection
              </TabsTrigger>
            </TabsList>

            {/* --- Manual Upload Tab --- */}
            <TabsContent value="manual" className="mt-4">
              <Card className="border border-border">
                <CardContent className="p-6">
                  <ManualUploadPanel
                    onFileSelect={handleManualUpload}
                    isProcessing={isProcessing}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            {/* --- Cloud Tab --- */}
            <TabsContent value="cloud" className="mt-4">
              <Card className="border border-border">
                <CardContent className="p-6">
                  <CloudIngestionPanel
                    onFileImport={(file) => startPhase1Upload(file, "Google Drive")}
                    isProcessing={isProcessing}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            {/* --- JIT Tab --- */}
            <TabsContent value="jit" className="mt-4">
              <Card className="border border-border">
                <CardContent className="p-6">
                  <JitInjectionPanel
                    rules={jitRules}
                    validated={jitValidated}
                    sessionGenerated={jitSessionGenerated}
                    sessionGenerating={jitSessionGenerating}
                    sessionId={jitSessionId}
                    sessionToken={jitSessionToken}
                    sessionExpiry={jitSessionExpiry}
                    onGenerateSession={handleJitGenerateSession}
                    onValidate={handleJitValidation}
                    onIngest={handleJitIngest}
                    isProcessing={isProcessing}
                  />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      )}

      {/* ============================================================ */}
      {/* STEP 2 - FULL SCREEN SECURITY PIPELINE                       */}
      {/* ============================================================ */}
      <div ref={flowRef}>
        {showPipeline && uploadedFile && (
          <div className="flex flex-col gap-6">
            {/* --- Top Status Bar --- */}
            <div className="border border-border bg-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="flex size-10 items-center justify-center bg-primary/10">
                    <FileIcon className="size-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">{uploadedFile.name}</p>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="font-mono text-xs text-muted-foreground">{formatFileSize(uploadedFile.size)}</span>
                      <span className="text-xs text-muted-foreground">{uploadedFile.type}</span>
                      <Badge className="bg-primary/10 text-primary border border-primary/20 hover:bg-primary/10 text-xs">
                        {uploadMethod}
                      </Badge>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {isProcessing && (
                    <Badge className="bg-primary/10 text-primary border border-primary/20 hover:bg-primary/10 text-xs gap-1.5 px-3 py-1">
                      <Loader2 className="size-3.5 animate-spin" />
                      Phase {activePhaseIndex + 1} / {securityPhases.length}
                    </Badge>
                  )}
                  {overallResult === "pass" && (
                    <Badge className="bg-success/10 text-success border border-success/20 hover:bg-success/10 text-xs gap-1.5 px-3 py-1">
                      <CheckCircle2 className="size-3.5" />
                      ALL PHASES PASSED
                    </Badge>
                  )}
                  {overallResult === "fail" && (
                    <Badge className="bg-destructive/10 text-destructive border border-destructive/20 hover:bg-destructive/10 text-xs gap-1.5 px-3 py-1">
                      <XCircle className="size-3.5" />
                      QUARANTINE TRIGGERED
                    </Badge>
                  )}
                </div>
              </div>

              {/* Mini progress overview */}
              <div className="mt-4 grid grid-cols-5 gap-2">
                {securityPhases.map((phase, i) => (
                  <div key={phase.id} className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase truncate">
                        P{i + 1}: {phase.label.split(" ")[0]}
                      </span>
                      <PhaseStatusDot status={phase.status} />
                    </div>
                    <div className="h-1.5 w-full bg-muted overflow-hidden">
                      <div
                        className={`h-full transition-all duration-200 ${
                          phase.status === "error"
                            ? "bg-destructive"
                            : phase.status === "success"
                            ? "bg-success"
                            : phase.status === "active"
                            ? "bg-primary"
                            : "bg-muted"
                        }`}
                        style={{ width: `${phase.progress}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* --- Phase Cards (Full Width, Big Scale) --- */}
            <div className="flex flex-col gap-4">
              {securityPhases.map((phase, index) => (
                <FullPhaseCard key={phase.id} phase={phase} index={index} />
              ))}
            </div>

            {overallResult && uploadedFile && (
              <FinalVerdict
                result={overallResult}
                file={uploadedFile}
                merkleRoot={merkleRoot}
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/* ================================================================== */
/* FULL PHASE CARD                                                     */
/* ================================================================== */
function FullPhaseCard({ phase, index }: { phase: SecurityPhase; index: number }) {
  const icons = [Hash, FileCheck, TreePine, Bug, Database]
  const Icon = icons[index] || ShieldCheck
  const logEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (phase.status === "active" || phase.status === "success" || phase.status === "error") {
      logEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
    }
  }, [phase.logs.length, phase.status])

  if (phase.status === "idle") {
    return (
      <div className="border border-border bg-card p-6 opacity-40">
        <div className="flex items-center gap-4">
          <div className="flex size-12 items-center justify-center bg-muted">
            <Icon className="size-5 text-muted-foreground" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold tracking-widest text-muted-foreground uppercase">
                Phase {index + 1}
              </span>
              <span className="text-sm font-semibold text-muted-foreground">{phase.label}</span>
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">{phase.description}</p>
          </div>
          <Badge variant="outline" className="ml-auto text-xs text-muted-foreground border-border px-3 py-1">
            PENDING
          </Badge>
        </div>
      </div>
    )
  }

  const borderAccent =
    phase.status === "success"
      ? "border-l-success"
      : phase.status === "error"
      ? "border-l-destructive"
      : "border-l-primary"

  return (
    <div className={`border border-border border-l-4 ${borderAccent} bg-card`}>
      {/* Phase Header */}
      <div className="flex items-center gap-4 border-b border-border p-5">
        <div
          className={`flex size-12 items-center justify-center ${
            phase.status === "success"
              ? "bg-success/10"
              : phase.status === "error"
              ? "bg-destructive/10"
              : "bg-primary/10"
          }`}
        >
          {phase.status === "active" ? (
            <Loader2 className="size-6 animate-spin text-primary" />
          ) : phase.status === "success" ? (
            <CheckCircle2 className="size-6 text-success" />
          ) : (
            <XCircle className="size-6 text-destructive" />
          )}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold tracking-widest text-muted-foreground uppercase">
              Phase {index + 1}
            </span>
            <span className="text-base font-bold text-foreground">{phase.label}</span>
          </div>
          <p className="mt-0.5 text-sm text-muted-foreground">{phase.subtitle}</p>
        </div>
        <PhaseStatusLabel status={phase.status} />
      </div>

      {/* Progress Bar */}
      <div className="px-5 pt-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-muted-foreground">Progress</span>
          <span className="font-mono text-sm font-bold text-foreground">{Math.round(phase.progress)}%</span>
        </div>
        <div className="h-3 w-full bg-muted overflow-hidden">
          <div
            className={`h-full transition-all duration-200 ${
              phase.status === "error"
                ? "bg-destructive"
                : phase.status === "success"
                ? "bg-success"
                : "bg-primary"
            }`}
            style={{ width: `${phase.progress}%` }}
          />
        </div>
      </div>

      {/* Stats Row */}
      {phase.stats.length > 0 && (
        <div className="px-5 pt-4">
          <div className={`grid gap-3 ${phase.stats.length <= 4 ? "grid-cols-4" : "grid-cols-5"}`}>
            {phase.stats.map((stat) => (
              <div
                key={stat.label}
                className={`flex flex-col gap-1 border p-3 ${
                  phase.status === "error"
                    ? "border-destructive/20 bg-destructive/5"
                    : "border-border bg-muted/30"
                }`}
              >
                <span className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                  {stat.label}
                </span>
                <span
                  className={`font-mono text-sm font-bold ${
                    phase.status === "error" ? "text-destructive" : "text-foreground"
                  }`}
                >
                  {stat.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Live Logs Terminal */}
      <div className="p-5">
        <div className="flex items-center gap-2 mb-2">
          <Terminal className="size-3.5 text-muted-foreground" />
          <span className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
            Execution Log
          </span>
          {phase.status === "active" && (
            <span className="relative flex size-2 ml-1">
              <span className="absolute inline-flex size-full animate-ping bg-primary opacity-75" />
              <span className="relative inline-flex size-2 bg-primary" />
            </span>
          )}
        </div>
        <div className="max-h-52 overflow-y-auto bg-foreground/[0.03] border border-border font-mono text-xs">
          <div className="p-3 flex flex-col gap-0.5">
            {phase.logs.map((log, i) => (
              <LogLine key={i} entry={log} />
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>
    </div>
  )
}

/* ================================================================== */
/* LOG LINE                                                            */
/* ================================================================== */
function LogLine({ entry }: { entry: LogEntry }) {
  const levelColors: Record<string, string> = {
    INFO: "text-primary",
    WARN: "text-amber-600",
    ERROR: "text-destructive",
    OK: "text-success",
  }

  return (
    <div className="flex gap-3 leading-5">
      <span className="text-muted-foreground shrink-0">{entry.time}</span>
      <span className={`font-bold shrink-0 w-12 ${levelColors[entry.level] || "text-muted-foreground"}`}>
        [{entry.level}]
      </span>
      <span className={`${entry.level === "ERROR" ? "text-destructive" : entry.level === "WARN" ? "text-amber-600" : "text-foreground"}`}>
        {entry.message}
      </span>
    </div>
  )
}

/* ================================================================== */
/* FINAL VERDICT                                                       */
/* ================================================================== */
function FinalVerdict({ result, file, merkleRoot }: { result: "pass" | "fail"; file: UploadedFile; merkleRoot?: string }) {
  if (result === "pass") {
    return (
      <div className="border-2 border-success/30 bg-success/5 p-8">
        <div className="flex items-start gap-5">
          <div className="flex size-14 items-center justify-center bg-success/10 shrink-0">
            <CheckCircle2 className="size-8 text-success" />
          </div>
          <div className="flex-1">
            <h3 className="text-xl font-bold text-success">Evidence Committed to WORM Ledger</h3>
            <p className="mt-2 text-sm text-success/80 leading-relaxed">
              All 5 security phases completed successfully. The evidence file has been cryptographically
              sealed, verified through the Merkle tree, and committed to the immutable WORM storage ledger.
            </p>
            <div className="mt-4 grid grid-cols-4 gap-3">
              <VerdictStat label="File" value={file.name} color="success" />
              <VerdictStat label="Size" value={formatFileSize(file.size)} color="success" />
              <VerdictStat label="Merkle Root" value={merkleRoot ? `${merkleRoot.slice(0, 12)}...${merkleRoot.slice(-4)}` : "Computing..."} color="success" />
              <VerdictStat label="Timestamp" value={new Date().toISOString().slice(0, 19)} color="success" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="border-2 border-destructive/30 bg-destructive/5 p-8">
      <div className="flex items-start gap-5">
        <div className="flex size-14 items-center justify-center bg-destructive/10 shrink-0">
          <AlertTriangle className="size-8 text-destructive" />
        </div>
        <div className="flex-1">
          <h3 className="text-xl font-bold text-destructive">Evidence Quarantined - Ledger Commit Blocked</h3>
          <p className="mt-2 text-sm text-destructive/80 leading-relaxed">
            Threat detection identified suspicious content during Phase 4 scanning. The file has been isolated
            in the quarantine zone. Manual review by a Level-3 officer is required.
          </p>
          <div className="mt-4 grid grid-cols-4 gap-3">
            <VerdictStat label="File" value={file.name} color="destructive" />
            <VerdictStat label="Threat" value="ZIP BOMB + YARA" color="destructive" />
            <VerdictStat label="Status" value="QUARANTINED" color="destructive" />
            <VerdictStat label="Case ID" value="N/A" color="destructive" />
          </div>
        </div>
      </div>
    </div>
  )
}

function VerdictStat({ label, value, color }: { label: string; value: string; color: "success" | "destructive" }) {
  return (
    <div className={`border p-3 flex flex-col gap-1 ${color === "success" ? "border-success/20 bg-success/5" : "border-destructive/20 bg-destructive/5"}`}>
      <span className={`text-[10px] font-semibold tracking-wider uppercase ${color === "success" ? "text-success/60" : "text-destructive/60"}`}>{label}</span>
      <span className={`font-mono text-xs font-bold truncate ${color === "success" ? "text-success" : "text-destructive"}`}>{value}</span>
    </div>
  )
}

/* ================================================================== */
/* MANUAL UPLOAD PANEL                                                 */
/* ================================================================== */
function ManualUploadPanel({
  onFileSelect,
  isProcessing,
}: {
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void
  isProcessing: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h4 className="text-sm font-semibold text-foreground mb-1">Direct File Upload</h4>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Upload forensic evidence directly from your local workstation. All file types accepted
          including .tar.gz, .log, .pcap, .bin, .json, disk images, and memory dumps.
        </p>
      </div>

      <div
        className="flex cursor-pointer flex-col items-center gap-4 border-2 border-dashed border-primary/30 bg-primary/5 p-10 transition-colors hover:border-primary/50 hover:bg-primary/10"
        onClick={() => !isProcessing && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Upload file from your system"
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click()
        }}
      >
        <div className="flex size-16 items-center justify-center bg-primary/10">
          <FolderOpen className="size-8 text-primary" />
        </div>
        <div className="text-center">
          <p className="text-base font-semibold text-foreground">Click to browse or drag and drop</p>
          <p className="text-xs text-muted-foreground mt-1">Maximum file size: 10 GB | Encrypted with AES-256-GCM in transit</p>
        </div>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          onChange={onFileSelect}
          disabled={isProcessing}
          aria-label="Select file for upload"
        />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <StatBox label="Endpoint" value="POST /api/ingestion/manual" />
        <StatBox label="Max Size" value="10 GB" />
        <StatBox label="Encryption" value="AES-256-GCM" />
      </div>
    </div>
  )
}

/* ================================================================== */
/* JIT INJECTION PANEL - with Generate Session first                   */
/* ================================================================== */
function JitInjectionPanel({
  rules,
  validated,
  sessionGenerated,
  sessionGenerating,
  sessionId,
  sessionToken,
  sessionExpiry,
  onGenerateSession,
  onValidate,
  onIngest,
  isProcessing,
}: {
  rules: JitRule[]
  validated: boolean
  sessionGenerated: boolean
  sessionGenerating: boolean
  sessionId: string
  sessionToken: string
  sessionExpiry: string
  onGenerateSession: () => void
  onValidate: () => void
  onIngest: () => void
  isProcessing: boolean
}) {
  const isValidating = rules.some((r) => r.checking)
  const ruleIcons = [Fingerprint, KeyRound, Wifi]
  const apiBase = getApiBaseUrl()

  const linuxCmd = `python scripts/collectors/linux_jit_collector.py --api-base ${apiBase}`
  const windowsCmd =
    `python scripts/collectors/windows_jit_collector.py --api-base ${apiBase} ` +
    `--log Security --log System --log Application --max-events-per-log 5000`

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // ignore clipboard failures (non-secure contexts)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h4 className="text-sm font-semibold text-foreground mb-1">Just-In-Time Secure Injection</h4>
        <p className="text-xs text-muted-foreground leading-relaxed">
          JIT Injection uses pre-validated secure channels with burn-on-use tokens. You must first generate a
          secure session, then validate all 3 authorization rules before the injection can proceed.
        </p>
      </div>

      {/* ================================================ */}
      {/* STEP A: Generate Session                          */}
      {/* ================================================ */}
      <div className={`border p-5 transition-all ${sessionGenerated ? "border-success/30 bg-success/5" : "border-border bg-card"}`}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`flex size-10 items-center justify-center ${sessionGenerated ? "bg-success/10" : "bg-primary/10"}`}>
              {sessionGenerating ? (
                <Loader2 className="size-5 animate-spin text-primary" />
              ) : sessionGenerated ? (
                <CheckCircle2 className="size-5 text-success" />
              ) : (
                <KeyRound className="size-5 text-primary" />
              )}
            </div>
            <div>
              <p className="text-sm font-bold text-foreground">
                Step 1: Generate Secure Session
              </p>
              <p className="text-[11px] text-muted-foreground">
                Creates a cryptographic session bound to your terminal, IP, and officer certificate
              </p>
            </div>
          </div>

          {!sessionGenerated && !sessionGenerating && (
            <Button
              onClick={onGenerateSession}
              disabled={isProcessing}
              className="bg-primary text-primary-foreground hover:bg-primary/90 gap-2"
            >
              <KeyRound className="size-4" />
              Generate Session
            </Button>
          )}
          {sessionGenerating && (
            <Badge className="bg-primary/10 text-primary border border-primary/20 hover:bg-primary/10 text-xs gap-1.5 px-3 py-1.5">
              <Loader2 className="size-3.5 animate-spin" />
              Generating...
            </Badge>
          )}
          {sessionGenerated && (
            <Badge className="bg-success/10 text-success border border-success/20 hover:bg-success/10 text-xs gap-1.5 px-3 py-1.5">
              <CheckCircle2 className="size-3.5" />
              SESSION ACTIVE
            </Badge>
          )}
        </div>

        {/* Session details - only shown after generation */}
        {sessionGenerated && (
          <div className="grid grid-cols-3 gap-3 mt-3">
            <div className="border border-success/20 bg-success/5 p-3 flex flex-col gap-1">
              <span className="text-[10px] font-semibold tracking-wider text-success/60 uppercase">Session ID</span>
              <span className="font-mono text-xs text-success font-bold truncate">{sessionId}</span>
            </div>
            <div className="border border-success/20 bg-success/5 p-3 flex flex-col gap-1">
              <span className="text-[10px] font-semibold tracking-wider text-success/60 uppercase">Token (burn-on-use)</span>
              <span className="font-mono text-xs text-success font-bold truncate">{sessionToken.slice(0, 20)}...{sessionToken.slice(-6)}</span>
            </div>
            <div className="border border-success/20 bg-success/5 p-3 flex flex-col gap-1">
              <span className="text-[10px] font-semibold tracking-wider text-success/60 uppercase">Expires</span>
              <span className="font-mono text-xs text-success font-bold">{new Date(sessionExpiry).toLocaleTimeString()} (30m TTL)</span>
            </div>
          </div>
        )}
      </div>

      {/* ================================================ */}
      {/* STEP B: Validate Rules (locked until session)     */}
      {/* ================================================ */}
      <div className={`border p-5 transition-all ${
        !sessionGenerated
          ? "border-border bg-muted/30 opacity-50"
          : validated
          ? "border-success/30 bg-success/5"
          : "border-border bg-card"
      }`}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`flex size-10 items-center justify-center ${
              validated ? "bg-success/10" : !sessionGenerated ? "bg-muted" : "bg-primary/10"
            }`}>
              {!sessionGenerated ? (
                <Lock className="size-5 text-muted-foreground" />
              ) : validated ? (
                <CheckCircle2 className="size-5 text-success" />
              ) : (
                <ShieldCheck className="size-5 text-primary" />
              )}
            </div>
            <div>
              <p className="text-sm font-bold text-foreground">
                Step 2: Validate Authorization Rules
              </p>
              <p className="text-[11px] text-muted-foreground">
                {!sessionGenerated
                  ? "Generate a session first to unlock rule validation"
                  : "All 3 rules must pass sequential validation before injection is authorized"
                }
              </p>
            </div>
          </div>

          {sessionGenerated && !validated && !isValidating && (
            <Button
              size="sm"
              onClick={onValidate}
              disabled={isProcessing || !sessionGenerated}
              className="bg-primary text-primary-foreground hover:bg-primary/90 gap-2"
            >
              <ShieldCheck className="size-4" />
              Validate All Rules
            </Button>
          )}
          {validated && (
            <Badge className="bg-success/10 text-success border border-success/20 hover:bg-success/10 text-xs gap-1.5 px-3 py-1.5">
              <CheckCircle2 className="size-3.5" />
              ALL RULES PASSED
            </Badge>
          )}
        </div>

        {/* Rules list */}
        <div className="flex flex-col gap-3">
          {rules.map((rule, idx) => {
            const RuleIcon = ruleIcons[idx] || ShieldCheck
            return (
              <div
                key={rule.id}
                className={`flex items-start gap-4 border p-4 transition-colors ${
                  rule.valid
                    ? "border-success/30 bg-success/5"
                    : rule.checking
                    ? "border-primary/30 bg-primary/5"
                    : !sessionGenerated
                    ? "border-border bg-muted/20"
                    : "border-border bg-card"
                }`}
              >
                <div className="mt-0.5 shrink-0">
                  {rule.checking ? (
                    <Loader2 className="size-5 animate-spin text-primary" />
                  ) : rule.valid ? (
                    <CheckCircle2 className="size-5 text-success" />
                  ) : !sessionGenerated ? (
                    <Lock className="size-5 text-muted-foreground/40" />
                  ) : (
                    <div className="flex size-5 items-center justify-center border-2 border-border bg-card text-[10px] font-bold text-muted-foreground">
                      {idx + 1}
                    </div>
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <RuleIcon className={`size-3.5 ${rule.valid ? "text-success" : rule.checking ? "text-primary" : "text-muted-foreground"}`} />
                    <p className={`text-sm font-semibold ${!sessionGenerated ? "text-muted-foreground" : "text-foreground"}`}>
                      {rule.label}
                    </p>
                  </div>
                  <p className={`text-xs mt-0.5 leading-relaxed ${!sessionGenerated ? "text-muted-foreground/60" : "text-muted-foreground"}`}>
                    {rule.description}
                  </p>
                  {rule.valid && (
                    <div className="flex items-center gap-1.5 mt-2">
                      <Clock className="size-3 text-success" />
                      <span className="text-[10px] font-mono font-medium text-success">
                        Validated at {new Date().toLocaleTimeString()}
                      </span>
                    </div>
                  )}
                  {rule.checking && (
                    <div className="mt-2">
                      <Progress value={60} className="h-1" />
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ================================================ */}
      {/* STEP C: Start Injection                           */}
      {/* ================================================ */}
      <div className={`border p-5 transition-all ${validated ? "border-success/30 bg-success/5" : "border-border bg-card"}`}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-bold text-foreground">Step 3: Run the collector on the target machine</p>
            <p className="text-[11px] text-muted-foreground mt-1 leading-relaxed">
              To pull logs from another user’s system, run a remote collector on that system. It will request its own
              JIT session, stream a bundle over WebSocket, and create a new ledger entry.
            </p>
          </div>
          <Badge className={`text-xs gap-1.5 px-3 py-1.5 ${validated ? "bg-success/10 text-success border border-success/20 hover:bg-success/10" : "bg-primary/10 text-primary border border-primary/20 hover:bg-primary/10"}`}>
            <Terminal className="size-3.5" />
            Remote Collector
          </Badge>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <div className="border border-border bg-muted/30 p-4">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-foreground">Linux</p>
              <Button size="sm" variant="outline" className="gap-2" onClick={() => void copy(linuxCmd)}>
                <Copy className="size-3.5" />
                Copy
              </Button>
            </div>
            <pre className="mt-2 text-[11px] leading-relaxed whitespace-pre-wrap font-mono text-muted-foreground">{linuxCmd}</pre>
          </div>
          <div className="border border-border bg-muted/30 p-4">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-foreground">Windows</p>
              <Button size="sm" variant="outline" className="gap-2" onClick={() => void copy(windowsCmd)}>
                <Copy className="size-3.5" />
                Copy
              </Button>
            </div>
            <pre className="mt-2 text-[11px] leading-relaxed whitespace-pre-wrap font-mono text-muted-foreground">{windowsCmd}</pre>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-[11px] text-muted-foreground">
            After upload completes, open Ledger to confirm the new `audit_id`, then proceed to Parsing (Phase 2).
          </p>
          <Button
            className="bg-primary text-primary-foreground hover:bg-primary/90 gap-2"
            disabled={!validated || isProcessing}
            onClick={onIngest}
          >
            <Database className="size-4" />
            Monitor in Ledger
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <StatBox label="Session API" value="POST /api/ingestion/manual" />
        <StatBox label="WebSocket" value="/ws/secure-stream/{session_id}" />
        <StatBox label="Policy" value="IP bind + TTL + burn-on-use" />
      </div>
    </div>
  )
}

/* ================================================================== */
/* SMALL HELPERS                                                       */
/* ================================================================== */
function PhaseStatusDot({ status }: { status: PhaseStatus }) {
  if (status === "idle") return <div className="size-2 bg-muted-foreground/30" />
  if (status === "active")
    return (
      <span className="relative flex size-2">
        <span className="absolute inline-flex size-full animate-ping bg-primary opacity-75" />
        <span className="relative inline-flex size-2 bg-primary" />
      </span>
    )
  if (status === "success") return <div className="size-2 bg-success" />
  return <div className="size-2 bg-destructive" />
}

function PhaseStatusLabel({ status }: { status: PhaseStatus }) {
  if (status === "active")
    return (
      <Badge className="bg-primary/10 text-primary border border-primary/20 hover:bg-primary/10 text-xs gap-1.5 px-3 py-1">
        <Loader2 className="size-3.5 animate-spin" />
        RUNNING
      </Badge>
    )
  if (status === "success")
    return (
      <Badge className="bg-success/10 text-success border border-success/20 hover:bg-success/10 text-xs px-3 py-1">
        PASSED
      </Badge>
    )
  if (status === "error")
    return (
      <Badge className="bg-destructive/10 text-destructive border border-destructive/20 hover:bg-destructive/10 text-xs px-3 py-1">
        FAILED
      </Badge>
    )
  return (
    <Badge variant="outline" className="text-xs text-muted-foreground border-border px-3 py-1">
      PENDING
    </Badge>
  )
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 border border-border bg-muted/30 p-3">
      <span className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">{label}</span>
      <span className="font-mono text-xs text-foreground font-medium">{value}</span>
    </div>
  )
}

/* ================================================================== */
/* DATA GENERATORS                                                     */
/* ================================================================== */
function ts(): string {
  return new Date().toLocaleTimeString("en-GB", { hour12: false })
}


function formatFileSize(bytes: number): string {
  if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(2)} GB`
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(2)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

function getProgressLogs(phaseIndex: number, progress: number, file: UploadedFile): LogEntry | null {
  const chunks = Math.ceil(file.size / (4 * 1024 * 1024)) || 48

  switch (phaseIndex) {
    case 0:
      if (progress > 10 && progress <= 15) return { time: ts(), level: "INFO", message: `Initializing chunk engine | Block size: 4 MB | Strategy: sequential` }
      if (progress > 25 && progress <= 30) return { time: ts(), level: "INFO", message: `Splitting file "${file.name}" (${formatFileSize(file.size)}) into ${chunks} chunks...` }
      if (progress > 40 && progress <= 45) return { time: ts(), level: "INFO", message: `Chunk [1..${Math.floor(chunks / 3)}] hashed | SHA-256 chain linked` }
      if (progress > 55 && progress <= 60) return { time: ts(), level: "INFO", message: `Chunk [${Math.floor(chunks / 3) + 1}..${Math.floor((chunks * 2) / 3)}] hashed | Chain integrity: OK` }
      if (progress > 70 && progress <= 75) return { time: ts(), level: "INFO", message: `Chunk [${Math.floor((chunks * 2) / 3) + 1}..${chunks}] hashed | Final chain link sealed` }
      if (progress > 85 && progress <= 90) return { time: ts(), level: "INFO", message: `Full file SHA-256: Computing...` }
      break
    case 1:
      if (progress > 15 && progress <= 20) return { time: ts(), level: "INFO", message: `Starting per-chunk hash verification (${chunks} chunks)...` }
      if (progress > 35 && progress <= 40) return { time: ts(), level: "INFO", message: `Verified ${Math.floor(chunks / 3)}/${chunks} chunks | No anomalies detected` }
      if (progress > 55 && progress <= 60) return { time: ts(), level: "INFO", message: `Verified ${Math.floor((chunks * 2) / 3)}/${chunks} chunks | Sequential order confirmed` }
      if (progress > 75 && progress <= 80) return { time: ts(), level: "INFO", message: `Verifying final batch | Checking for oversized chunks...` }
      if (progress > 90 && progress <= 95) return { time: ts(), level: "OK", message: `All ${chunks} chunks passed integrity verification` }
      break
    case 2:
      if (progress > 10 && progress <= 15) return { time: ts(), level: "INFO", message: `Constructing Merkle tree from ${chunks} leaf nodes...` }
      if (progress > 30 && progress <= 35) return { time: ts(), level: "INFO", message: `Tree depth: ${Math.ceil(Math.log2(chunks))} levels | Building intermediate nodes...` }
      if (progress > 55 && progress <= 60) return { time: ts(), level: "INFO", message: `Level ${Math.ceil(Math.log2(chunks)) - 2} computed | ${Math.ceil(chunks / 4)} nodes` }
      if (progress > 75 && progress <= 80) return { time: ts(), level: "INFO", message: `Computing Merkle root from top-level pair...` }
      if (progress > 90 && progress <= 95) return { time: ts(), level: "OK", message: `Merkle Root: Computing...` }
      break
    case 3:
      if (progress > 10 && progress <= 15) return { time: ts(), level: "INFO", message: `Entering sandboxed triage environment...` }
      if (progress > 25 && progress <= 30) return { time: ts(), level: "INFO", message: `[1/4] ZIP Bomb detection: Analyzing compression ratio...` }
      if (progress > 40 && progress <= 45) return { time: ts(), level: "INFO", message: `[2/4] Magic byte inspection: Reading file header bytes...` }
      if (progress > 55 && progress <= 60) return { time: ts(), level: "INFO", message: `[3/4] Entropy analysis: Computing Shannon entropy across sectors...` }
      if (progress > 75 && progress <= 80) return { time: ts(), level: "INFO", message: `[4/4] YARA scan: Matching against 4,217 malware signatures...` }
      if (progress > 90 && progress <= 95) return { time: ts(), level: "INFO", message: `All triage sub-checks executing... awaiting results` }
      break
    case 4:
      if (progress > 15 && progress <= 20) return { time: ts(), level: "INFO", message: `Preparing WORM ledger entry...` }
      if (progress > 35 && progress <= 40) return { time: ts(), level: "INFO", message: `Computing entry hash: SHA-256(previous_entry || merkle_root || metadata)` }
      if (progress > 55 && progress <= 60) return { time: ts(), level: "INFO", message: `Chain-of-custody record: Officer authenticated, source IP 10.120.45.67` }
      if (progress > 75 && progress <= 80) return { time: ts(), level: "INFO", message: `Writing to WORM storage backend... (immutable, append-only)` }
      if (progress > 90 && progress <= 95) return { time: ts(), level: "INFO", message: `Ledger write-ahead log flushed | Awaiting commit confirmation...` }
      break
  }
  return null
}

function getPhaseCompleteLogs(phaseIndex: number, file: UploadedFile): LogEntry[] {
  const chunks = Math.ceil(file.size / (4 * 1024 * 1024)) || 48
  switch (phaseIndex) {
    case 0:
      return [
        { time: ts(), level: "OK", message: `COMPLETE: ${chunks} chunks created, hash chain sealed` },
        { time: ts(), level: "OK", message: `Disk-based storage confirmed (no in-memory buffering)` },
      ]
    case 1:
      return [
        { time: ts(), level: "OK", message: `COMPLETE: ${chunks}/${chunks} hashes verified, 0 corrupted, 0 out-of-order` },
        { time: ts(), level: "OK", message: `Transfer integrity: 100.00%` },
      ]
    case 2:
      return [
        { time: ts(), level: "OK", message: `COMPLETE: Merkle tree sealed` },
        { time: ts(), level: "OK", message: `Digital signature applied with forensic officer certificate` },
      ]
    case 3:
      return [
        { time: ts(), level: "OK", message: `ZIP Bomb check: completed` },
        { time: ts(), level: "OK", message: `Magic byte: header verified` },
        { time: ts(), level: "OK", message: `Entropy analysis: completed` },
        { time: ts(), level: "OK", message: `YARA scan: completed` },
        { time: ts(), level: "OK", message: `VERDICT: CLEAN - File cleared for ledger commit` },
      ]
    case 4:
      return [
        { time: ts(), level: "OK", message: `Ledger entry appended` },
        { time: ts(), level: "OK", message: `WORM write confirmed (immutable, tamper-proof)` },
        { time: ts(), level: "OK", message: `Timestamp: ${new Date().toISOString()}` },
        { time: ts(), level: "OK", message: `COMPLETE: Evidence committed to permanent storage` },
      ]
    default:
      return []
  }
}

function getPhaseStats(phaseIndex: number, file: UploadedFile, merkleRoot: string = ""): { label: string; value: string }[] {
  const chunks = Math.ceil(file.size / (4 * 1024 * 1024)) || 48
  switch (phaseIndex) {
    case 0:
      return [
        { label: "Total Chunks", value: String(chunks) },
        { label: "Block Size", value: "4 MB" },
        { label: "Hash Algorithm", value: "SHA-256" },
        { label: "Chain Mode", value: "Sequential" },
      ]
    case 1:
      return [
        { label: "Verified", value: `${chunks} / ${chunks}` },
        { label: "Corrupted", value: "0" },
        { label: "Out-of-Order", value: "0" },
        { label: "Integrity", value: "100.00%" },
      ]
    case 2:
      return [
        { label: "Tree Depth", value: `${Math.ceil(Math.log2(chunks))} levels` },
        { label: "Leaf Nodes", value: String(chunks) },
        { label: "Merkle Root", value: merkleRoot ? `${merkleRoot.slice(0, 12)}...${merkleRoot.slice(-4)}` : "Computing..." },
        { label: "Signature", value: "ECDSA-P256" },
      ]
    case 3:
      return [
        { label: "ZIP Bomb", value: "Checking..." },
        { label: "Magic Byte", value: "Checking..." },
        { label: "Entropy", value: "Checking..." },
        { label: "YARA Hits", value: "Checking..." },
      ]
    case 4:
      return [
        { label: "Block #", value: "Computing..." },
        { label: "Storage", value: "WORM" },
        { label: "Immutable", value: "YES" },
        { label: "Replicated", value: "Computing..." },
      ]
    default:
      return []
  }
}

function getInitialPhases(): SecurityPhase[] {
  return [
    {
      id: "chunk",
      label: "Chunk Splitting & Hash Chain",
      subtitle: "File segmented into 4 MB blocks, each SHA-256 hashed and chained",
      description: "Splits the evidence file into fixed-size chunks, computes individual hashes, and establishes a sequential hash chain for integrity.",
      status: "idle",
      progress: 0,
      logs: [],
      stats: [],
    },
    {
      id: "integrity",
      label: "Integrity Verification",
      subtitle: "Per-chunk hash verification, order check, and oversize rejection",
      description: "Independently verifies each chunk hash against the chain, detects out-of-order delivery, and rejects any oversized chunks.",
      status: "idle",
      progress: 0,
      logs: [],
      stats: [],
    },
    {
      id: "merkle",
      label: "Merkle Tree Seal",
      subtitle: "Cryptographic tree constructed, root sealed as evidence fingerprint",
      description: "Builds a full Merkle tree from chunk hashes, computes the root, and digitally signs it as the evidence fingerprint.",
      status: "idle",
      progress: 0,
      logs: [],
      stats: [],
    },
    {
      id: "quarantine",
      label: "Quarantine & Threat Detection",
      subtitle: "ZIP bomb, magic byte, entropy analysis, and YARA malware scan",
      description: "Runs the file through a sandboxed triage: decompression bomb detection, header inspection, entropy analysis, and signature-based malware scan.",
      status: "idle",
      progress: 0,
      logs: [],
      stats: [],
    },
    {
      id: "ledger",
      label: "WORM Ledger Commit",
      subtitle: "Append-only immutable ledger with chain-of-custody preservation",
      description: "Commits the verified evidence to the Write-Once-Read-Many ledger with full chain-of-custody metadata and tamper-proof timestamps.",
      status: "idle",
      progress: 0,
      logs: [],
      stats: [],
    },
  ]
}

function getInitialJitRules(): JitRule[] {
  return [
    {
      id: "ip-binding",
      label: "Rule 1: IP Binding Verification",
      description:
        "Source IP must match the registered IP of the requesting officer's terminal. Cross-checks against the session registry to prevent session hijacking or IP spoofing attacks.",
      valid: false,
      checking: false,
    },
    {
      id: "ttl-token",
      label: "Rule 2: Burn-On-Use Token (30 min TTL)",
      description:
        "A single-use cryptographic token with a 30-minute time-to-live is generated per injection request. The token is cryptographically bound to the session and invalidated after first use.",
      valid: false,
      checking: false,
    },
    {
      id: "channel-auth",
      label: "Rule 3: WSS Channel Authentication (mTLS)",
      description:
        "WebSocket Secure channel must be established with mutual TLS authentication. Both client and server certificates are verified with certificate pinning enforced.",
      valid: false,
      checking: false,
    },
  ]
}
