'use client'

import { useEffect, useCallback, useState, useRef } from 'react'
import { api } from '@operation-room/lib/api'
import { useStudioStore, type PanelId } from '../store/useStudioStore'

/**
 * usePanelData — standardized data-loading hook for all module panels.
 * 
 * Handles: loading state, error state, retry, and badge count reporting.
 * 
 * Usage:
 *   const { data, loading, error, refresh } = usePanelData({
 *     panelId: 'timeline',
 *     caseId,
 *     endpoint: `/cases/${caseId}/timeline/stats`,
 *     badgeExtractor: (data) => data?.total_events ?? 0,
 *   })
 */

interface UsePanelDataOptions<T> {
  panelId: PanelId
  caseId: string
  endpoint: string
  /** Extract badge count from the loaded data (optional) */
  badgeExtractor?: (data: T | null) => number
  /** Transform raw API response (optional) */
  transform?: (raw: any) => T | null
  /** Auto-load on mount (default: true) */
  autoLoad?: boolean
}

interface UsePanelDataResult<T> {
  data: T | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export function usePanelData<T = any>({
  panelId,
  caseId,
  endpoint,
  badgeExtractor,
  transform,
  autoLoad = true,
}: UsePanelDataOptions<T>): UsePanelDataResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const setPanelBadge = useStudioStore((s) => s.setPanelBadge)
  const loadedRef = useRef(false)

  const load = useCallback(async () => {
    if (!caseId) return
    try {
      setLoading(true)
      setError(null)
      const raw = await api.get(endpoint).catch(() => null)

      if (raw?.error) {
        // Treat "no data" responses as empty state
        const errMsg = typeof raw.error === 'string' ? raw.error : 'Failed to load'
        if (errMsg.includes('No') || errMsg.includes('not found')) {
          setData(null)
          setPanelBadge(panelId, 0)
          return
        }
        setError(errMsg)
        return
      }

      const result = transform ? transform(raw) : (raw as T)
      setData(result)

      // Report badge count
      if (badgeExtractor && result) {
        const count = badgeExtractor(result)
        setPanelBadge(panelId, count)
      }
    } catch (err) {
      console.warn(`[${panelId}Panel] Load failed:`, err)
      setError(`Failed to load ${panelId} data`)
    } finally {
      setLoading(false)
    }
  }, [caseId, endpoint, panelId, transform, badgeExtractor, setPanelBadge])

  useEffect(() => {
    if (autoLoad && !loadedRef.current) {
      loadedRef.current = true
      load()
    }
  }, [autoLoad, load])

  return { data, loading, error, refresh: load }
}
