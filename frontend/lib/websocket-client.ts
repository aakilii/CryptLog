import { getWsBaseUrl } from '@/lib/public-env'

const WS_BASE_URL = getWsBaseUrl()

export interface ChunkMessage {
  chunk_number: number
  chunk_hash: string
  data: string
  is_final: boolean
}

export interface ServerResponse {
  status: 'ok' | 'error' | 'done'
  chunk_number?: number
  detail?: string
  audit_id?: string
  sha256?: string
  file_path?: string
  merkle_root?: string
  binary_signature?: string
  result?: {
    status: string
    audit_id: string
    sha256: string
    file_path: string
    merkle_root?: string
    binary_signature: string
  }
}

export interface UploadProgress {
  chunkNumber: number
  totalChunks: number
  bytesUploaded: number
  totalBytes: number
  percentage: number
}

export type UploadProgressCallback = (progress: UploadProgress) => void
export type UploadCompleteCallback = (result: ServerResponse) => void
export type UploadErrorCallback = (error: Error) => void

/** Must match backend `MAX_CHUNKS` in app/ingestion/ws_router.py */
const BACKEND_MAX_CHUNKS = 10_000

/** Binary chunk magic + header: WSC1 | u32 chunk | u8 flags | u32 len | 32-byte SHA256 | payload */
const WS_CHUNK_MAGIC = new TextEncoder().encode('WSC1')
const WS_CHUNK_HEADER_SIZE = 4 + 4 + 1 + 4 + 32

function hexToBytes(hex: string): Uint8Array {
  const out = new Uint8Array(hex.length / 2)
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16)
  }
  return out
}

export class WebSocketUploadClient {
  private ws: WebSocket | null = null
  private sessionId: string
  private wsUrl: string
  private chunkSize: number = 64 * 1024
  /** When true, send raw chunk frames (no base64/JSON) for lower CPU and wire size. */
  private useBinaryChunks: boolean = true
  private onProgress: UploadProgressCallback | null = null
  private onComplete: UploadCompleteCallback | null = null
  private onError: UploadErrorCallback | null = null

  constructor(sessionId: string, wsBaseUrl?: string) {
    this.sessionId = sessionId
    const baseUrl = wsBaseUrl || WS_BASE_URL
    this.wsUrl = `${baseUrl}/ws/secure-stream/${sessionId}`
  }

  /** Disable binary frames (JSON+base64 only); for compatibility testing. */
  setUseBinaryChunks(enabled: boolean) {
    this.useBinaryChunks = enabled
  }

  setProgressCallback(callback: UploadProgressCallback) {
    this.onProgress = callback
  }

  setCompleteCallback(callback: UploadCompleteCallback) {
    this.onComplete = callback
  }

  setErrorCallback(callback: UploadErrorCallback) {
    this.onError = callback
  }

  async uploadFile(file: File): Promise<ServerResponse> {
    return new Promise((resolve, reject) => {
      try {
        // Keep chunk count under backend cap (MAX_CHUNKS=10_000) by scaling chunk size.
        // Backend also enforces MAX_CHUNK_SIZE_BYTES=5MB (pre-base64 decode).
        this.chunkSize = this.pickChunkSize(file.size)

        this.ws = new WebSocket(this.wsUrl)

        this.ws.onopen = () => {
          // Send meta first so backend uses original filename in WORM + ledger.
          try {
            this.ws?.send(JSON.stringify({ type: 'meta', filename: file.name }))
          } catch {
            // ignore
          }
          this.sendFileChunks(file)
        }

        this.ws.onmessage = (event) => {
          try {
            const response: ServerResponse = JSON.parse(event.data)

            if (response.status === 'error') {
              const error = new Error(response.detail || 'Upload failed')
              this.onError?.(error)
              reject(error)
              this.close()
              return
            }

            if (response.status === 'ok' && response.chunk_number !== undefined) {
              const totalChunks = Math.ceil(file.size / this.chunkSize)
              const progress: UploadProgress = {
                chunkNumber: response.chunk_number + 1,
                totalChunks,
                bytesUploaded: Math.min((response.chunk_number + 1) * this.chunkSize, file.size),
                totalBytes: file.size,
                percentage: Math.round(((response.chunk_number + 1) / totalChunks) * 100),
              }
              this.onProgress?.(progress)
            }

            if (response.status === 'done') {
              const result = response.result || response
              this.onComplete?.(result)
              resolve(result)
              this.close()
            }
          } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to parse server response')
            this.onError?.(error)
            reject(error)
            this.close()
          }
        }

        this.ws.onerror = (event) => {
          const error = new Error('WebSocket connection error')
          this.onError?.(error)
          reject(error)
          this.close()
        }

        this.ws.onclose = (event) => {
          if (event.code !== 1000 && event.code !== 1001) {
            const error = new Error(`WebSocket closed unexpectedly: ${event.code} ${event.reason || ''}`)
            this.onError?.(error)
            reject(error)
          }
        }
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to create WebSocket connection')
        this.onError?.(error)
        reject(error)
      }
    })
  }

  private async sendFileChunks(file: File) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not open')
    }

    const totalChunks = Math.ceil(file.size / this.chunkSize)
    const reader = new FileReader()

    let chunkNumber = 0
    let offset = 0

    const readNextChunk = () => {
      if (chunkNumber >= totalChunks) {
        return
      }

      const chunk = file.slice(offset, offset + this.chunkSize)
      reader.readAsArrayBuffer(chunk)
    }

    reader.onload = async (e) => {
      if (!e.target?.result || !(e.target.result instanceof ArrayBuffer)) {
        return
      }

      const chunkData = new Uint8Array(e.target.result)

      const hashBuffer = await crypto.subtle.digest('SHA-256', chunkData)
      const hashArray = Array.from(new Uint8Array(hashBuffer))
      const chunkHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')

      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        const isFinal = chunkNumber === totalChunks - 1
        if (this.useBinaryChunks) {
          const hashBytes = hexToBytes(chunkHash)
          const frame = new Uint8Array(WS_CHUNK_HEADER_SIZE + chunkData.length)
          frame.set(WS_CHUNK_MAGIC, 0)
          const dv = new DataView(frame.buffer)
          dv.setUint32(4, chunkNumber, false)
          frame[8] = isFinal ? 1 : 0
          dv.setUint32(9, chunkData.length, false)
          frame.set(hashBytes, 13)
          frame.set(chunkData, WS_CHUNK_HEADER_SIZE)
          this.ws.send(frame.buffer)
        } else {
          const message: ChunkMessage = {
            chunk_number: chunkNumber,
            chunk_hash: chunkHash,
            data: this.uint8ToBase64(chunkData),
            is_final: isFinal,
          }
          this.ws.send(JSON.stringify(message))
        }
        chunkNumber++
        offset += this.chunkSize

        if (chunkNumber < totalChunks) {
          readNextChunk()
        }
      }
    }

    reader.onerror = () => {
      const error = new Error('Failed to read file chunk')
      this.onError?.(error)
      this.close()
    }

    readNextChunk()
  }

  private pickChunkSize(totalBytes: number): number {
    const MAX_CHUNK_BYTES = 5 * 1024 * 1024 // must match backend MAX_CHUNK_SIZE_BYTES
    const MIN_CHUNK_BYTES = 64 * 1024
    const margin = 500 // stay under BACKEND_MAX_CHUNKS
    const maxAllowed = Math.max(1, BACKEND_MAX_CHUNKS - margin)

    // Prefer 5MB chunks whenever chunk count stays under the backend cap (large uploads).
    const chunksIfMax = Math.ceil(totalBytes / MAX_CHUNK_BYTES)
    if (chunksIfMax <= maxAllowed) {
      return MAX_CHUNK_BYTES
    }

    const desired = Math.ceil(totalBytes / maxAllowed)
    const clamped = Math.min(MAX_CHUNK_BYTES, Math.max(MIN_CHUNK_BYTES, desired))
    const boundary = 64 * 1024
    return Math.min(MAX_CHUNK_BYTES, Math.ceil(clamped / boundary) * boundary)
  }

  private uint8ToBase64(bytes: Uint8Array): string {
    // Avoid call stack blowups from String.fromCharCode(...bigArray).
    const chunk = 0x8000
    let binary = ''
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunk))
    }
    return btoa(binary)
  }

  close() {
    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close(1000, 'Upload complete')
      }
      this.ws = null
    }
  }

  abort() {
    if (this.ws) {
      this.ws.close(1003, 'Upload aborted by user')
      this.ws = null
    }
  }
}


