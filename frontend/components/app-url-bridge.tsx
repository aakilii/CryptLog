"use client"

import { useEffect } from "react"
import { useSearchParams } from "next/navigation"
import { useApp } from "@/lib/app-context"
import { APP_PAGE_QUERY, parseShellPage } from "@/lib/app-navigation"

/**
 * Hydrates `currentPage` from the URL on load and when the query string changes.
 * `?page=dashboard|ingestion|…` selects the shell view.
 */
export function AppUrlBridge() {
  const searchParams = useSearchParams()
  const { setCurrentPage, isAuthenticated } = useApp()

  useEffect(() => {
    if (!isAuthenticated) return
    const shell = parseShellPage(searchParams.get(APP_PAGE_QUERY))
    if (shell) setCurrentPage(shell)
  }, [isAuthenticated, searchParams, setCurrentPage])

  return null
}
