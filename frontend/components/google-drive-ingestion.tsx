"use client"

import { useCallback, useEffect, useState } from "react"
import Script from "next/script"
import { HardDrive, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  driveFileIdToBrowserFile,
  loadGooglePickerApi,
  openDrivePicker,
  requestDriveAccessToken,
} from "@/lib/google-drive-ingest"
import { publicEnv } from "@/lib/public-env"

type Props = {
  onFileImport: (file: File) => Promise<void>
  isProcessing: boolean
}

type Phase = "idle" | "sign-in" | "picker" | "pull"

export function GoogleDriveIngestion({ onFileImport, isProcessing }: Props) {
  const [cfgReady, setCfgReady] = useState(false)
  const [clientId, setClientId] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [phase, setPhase] = useState<Phase>("idle")

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const r = await fetch("/api/config/public", { cache: "no-store" })
        const d = (await r.json()) as { googleClientId?: string; googleApiKey?: string }
        if (cancelled) return
        setClientId((d.googleClientId ?? "").trim() || publicEnv.googleClientId)
        setApiKey((d.googleApiKey ?? "").trim() || publicEnv.googleApiKey)
      } catch {
        if (!cancelled) {
          setClientId(publicEnv.googleClientId)
          setApiKey(publicEnv.googleApiKey)
        }
      } finally {
        if (!cancelled) setCfgReady(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const configured = clientId.length > 0 && apiKey.length > 0
  const busy = phase !== "idle" || isProcessing

  const start = useCallback(async () => {
    if (!configured) {
      toast("Configure Google Drive", {
        description:
          "Set NEXT_PUBLIC_GOOGLE_CLIENT_ID and NEXT_PUBLIC_GOOGLE_API_KEY in .env.local, then restart dev.",
      })
      return
    }
    try {
      setPhase("sign-in")
      const token = await requestDriveAccessToken(clientId)
      setPhase("picker")
      await loadGooglePickerApi()
      setPhase("idle")

      openDrivePicker(token, apiKey, (fileId) => {
        void (async () => {
          try {
            setPhase("pull")
            const file = await driveFileIdToBrowserFile(fileId, token)
            await onFileImport(file)
          } catch (e) {
            console.error(e)
            toast.error(e instanceof Error ? e.message : "Could not download that file from Drive.")
          } finally {
            setPhase("idle")
          }
        })()
      })
    } catch (e) {
      console.error(e)
      const msg = e instanceof Error ? e.message : "Google sign-in was cancelled or failed."
      if (!/popup|closed|cancel/i.test(msg)) {
        toast.error(msg)
      }
      setPhase("idle")
    }
  }, [apiKey, clientId, configured, onFileImport])

  const label =
    phase === "sign-in"
      ? "Signing in…"
      : phase === "picker"
        ? "Opening picker…"
        : phase === "pull"
          ? "Downloading…"
          : "Choose from Google Drive"

  return (
    <>
      <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" />
      <Script src="https://apis.google.com/js/api.js" strategy="afterInteractive" />

      <Card className="border-dashed shadow-none">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <div className="flex size-9 items-center justify-center rounded-lg bg-muted">
              <HardDrive className="size-4 text-foreground" />
            </div>
            <div>
              <CardTitle className="text-base">Google Drive</CardTitle>
              <CardDescription className="text-xs mt-1 max-w-prose">
                OAuth and the official Picker. Workspace files export as PDF / Office; binaries download as stored.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-0">
          {cfgReady && !configured && (
            <Alert>
              <AlertTitle className="text-sm">Credentials missing</AlertTitle>
              <AlertDescription className="text-xs text-muted-foreground">
                Add <code className="rounded bg-muted px-1">NEXT_PUBLIC_GOOGLE_CLIENT_ID</code> and{" "}
                <code className="rounded bg-muted px-1">NEXT_PUBLIC_GOOGLE_API_KEY</code> to{" "}
                <code className="rounded bg-muted px-1">frontend/.env.local</code>. Enable Drive API and Picker API in
                Google Cloud, then restart <code className="rounded bg-muted px-1">npm run dev</code>.
              </AlertDescription>
            </Alert>
          )}

          <Button
            type="button"
            onClick={() => void start()}
            disabled={!cfgReady || !configured || busy}
            className="w-full sm:w-auto gap-2"
          >
            {phase !== "idle" ? <Loader2 className="size-4 animate-spin shrink-0" aria-hidden /> : null}
            {label}
          </Button>
        </CardContent>
      </Card>
    </>
  )
}

/** Kept for a stable import path from the ingestion page. */
export { GoogleDriveIngestion as CloudIngestionPanel }
