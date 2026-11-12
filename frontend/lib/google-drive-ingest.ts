/**
 * Google Drive → File (browser): OAuth token, Picker, Drive v3 download/export.
 * No React; safe to unit-test or reuse from workers if ever needed.
 */

export const DRIVE_OAUTH_SCOPES = [
  "https://www.googleapis.com/auth/drive.readonly",
  "https://www.googleapis.com/auth/drive.metadata.readonly",
].join(" ")

const PICKER_MIME_TYPES = [
  "application/pdf",
  "application/zip",
  "application/x-zip-compressed",
  "application/gzip",
  "application/x-gzip",
  "application/x-tar",
  "text/plain",
  "text/csv",
  "application/json",
  "application/xml",
  "text/xml",
  "application/octet-stream",
  "application/vnd.google-apps.document",
  "application/vnd.google-apps.spreadsheet",
  "application/vnd.google-apps.presentation",
  "application/vnd.google-apps.drawing",
].join(",")

const WORKSPACE_EXPORT: Record<string, string> = {
  "application/vnd.google-apps.document": "application/pdf",
  "application/vnd.google-apps.spreadsheet":
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.google-apps.presentation":
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/vnd.google-apps.drawing": "image/png",
}

function suffixForExportMime(m: string): string {
  if (m === "application/pdf") return ".pdf"
  if (m.includes("spreadsheetml.sheet")) return ".xlsx"
  if (m.includes("presentationml.presentation")) return ".pptx"
  if (m === "image/png") return ".png"
  return ""
}

async function driveJson<T>(url: string, token: string): Promise<T> {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) {
    const t = await res.text().catch(() => "")
    throw new Error(`${res.status} ${res.statusText}${t ? `: ${t.slice(0, 200)}` : ""}`)
  }
  return res.json() as Promise<T>
}

async function driveBlob(url: string, token: string): Promise<Blob> {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) {
    const t = await res.text().catch(() => "")
    throw new Error(`${res.status} ${res.statusText}${t ? `: ${t.slice(0, 200)}` : ""}`)
  }
  return res.blob()
}

export async function driveFileIdToBrowserFile(fileId: string, accessToken: string): Promise<File> {
  const meta = await driveJson<{ name?: string; mimeType?: string }>(
    `https://www.googleapis.com/drive/v3/files/${encodeURIComponent(fileId)}?fields=id,name,mimeType`,
    accessToken,
  )
  const mime = meta.mimeType || ""

  if (mime === "application/vnd.google-apps.folder") {
    throw new Error("Choose a file, not a folder.")
  }
  if (mime.startsWith("application/vnd.google-apps.") && !WORKSPACE_EXPORT[mime]) {
    throw new Error(
      "This Google file type cannot be exported here. Export it from Drive first, then select that file.",
    )
  }

  let blob: Blob
  let filename = meta.name || `drive-${fileId}`
  let outMime: string

  const exportMime = WORKSPACE_EXPORT[mime]
  if (exportMime) {
    const u = new URL(
      `https://www.googleapis.com/drive/v3/files/${encodeURIComponent(fileId)}/export`,
    )
    u.searchParams.set("mimeType", exportMime)
    blob = await driveBlob(u.toString(), accessToken)
    const sfx = suffixForExportMime(exportMime)
    if (sfx && !filename.toLowerCase().endsWith(sfx)) filename += sfx
    outMime = exportMime
  } else {
    const u = `https://www.googleapis.com/drive/v3/files/${encodeURIComponent(fileId)}?alt=media`
    blob = await driveBlob(u, accessToken)
    outMime = mime || blob.type || "application/octet-stream"
  }

  return new File([blob], filename, { type: outMime })
}

export function loadGooglePickerApi(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!window.gapi?.load) {
      reject(new Error("Google API script not ready yet."))
      return
    }
    window.gapi.load("picker", () => resolve())
  })
}

export function requestDriveAccessToken(clientId: string): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!window.google?.accounts?.oauth2?.initTokenClient) {
      reject(new Error("Google Sign-In not loaded yet."))
      return
    }
    const client = window.google.accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: DRIVE_OAUTH_SCOPES,
      callback: (res) => {
        if (res.error) {
          reject(new Error(res.error_description || res.error))
          return
        }
        if (res.access_token) resolve(res.access_token)
        else reject(new Error("No access token returned."))
      },
      error_callback: (err) => reject(err instanceof Error ? err : new Error(String(err))),
    })
    client.requestAccessToken({ prompt: "" })
  })
}

export function openDrivePicker(
  accessToken: string,
  developerKey: string,
  onFileId: (fileId: string) => void,
): void {
  const view = new window.google.picker.DocsView(window.google.picker.ViewId.DOCS).setMimeTypes(
    PICKER_MIME_TYPES,
  )
  const picker = new window.google.picker.PickerBuilder()
    .addView(view)
    .setOAuthToken(accessToken)
    .setDeveloperKey(developerKey)
    .setCallback((data: { action?: string; [k: string]: unknown }) => {
      if (data.action === window.google.picker.Action.PICKED) {
        const docs = data[window.google.picker.Response.DOCUMENTS] as { id?: string }[] | undefined
        const id = docs?.[0]?.id
        if (id) onFileId(id)
      }
    })
    .build()
  picker.setVisible(true)
}
