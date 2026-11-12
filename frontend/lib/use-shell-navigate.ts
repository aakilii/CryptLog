"use client"

import { useCallback } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { useApp } from "@/lib/app-context"
import type { ShellPage } from "@/lib/app-navigation"
import { APP_PAGE_QUERY } from "@/lib/app-navigation"

/**
 * Keeps the address bar in sync with the Sakshi Ledger shell: `?page=…`.
 */
export function useShellNavigate() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { setCurrentPage } = useApp()

  const go = useCallback(
    (page: ShellPage) => {
      setCurrentPage(page)
      const next = new URLSearchParams(searchParams.toString())
      next.set(APP_PAGE_QUERY, page)
      const q = next.toString()
      router.replace(q ? `${pathname}?${q}` : pathname)
    },
    [pathname, router, searchParams, setCurrentPage]
  )

  return { go }
}
