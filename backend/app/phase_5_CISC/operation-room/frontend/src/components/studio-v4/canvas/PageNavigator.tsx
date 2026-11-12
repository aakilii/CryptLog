import React from 'react'
import { Button } from '@operation-room/components/ui/button'
import { useStudioStore } from '../store/useStudioStore'
import { cn } from '@operation-room/lib/utils'
import { Plus, Trash2 } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@operation-room/components/ui/dropdown-menu'

interface PageNavigatorProps {
  className?: string
}

export const PageNavigator = ({ className }: PageNavigatorProps) => {
  const { pages, currentPage, setCurrentPage, addPage, deletePage } = useStudioStore()

  const scrollToPage = (index: number) => {
    setCurrentPage(index)
    const el = document.getElementById(`page-${pages[index]?.id}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <span className="font-ui text-[10px] text-muted-foreground uppercase tracking-wider mr-1">Pages</span>
      <div className="flex items-center gap-0.5">
        {pages.map((page, i) => (
          <DropdownMenu key={page.id}>
            <DropdownMenuTrigger asChild>
              <Button
                variant={currentPage === i ? "secondary" : "ghost"}
                size="sm"
                className={cn(
                  "h-6 w-6 p-0 font-geist-mono text-[10px] font-medium rounded-md",
                  currentPage === i && "ring-1 ring-sky-400/30 shadow-sm"
                )}
                onClick={() => scrollToPage(i)}
              >
                {i + 1}
              </Button>
            </DropdownMenuTrigger>
            {pages.length > 1 && (
              <DropdownMenuContent align="start" side="top" sideOffset={8}>
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive gap-2 text-xs"
                  onClick={() => deletePage(i)}
                >
                  <Trash2 className="h-3 w-3" />
                  Delete page {i + 1}
                </DropdownMenuItem>
              </DropdownMenuContent>
            )}
          </DropdownMenu>
        ))}
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="h-6 px-1.5 font-ui text-[10px] gap-1 text-muted-foreground hover:text-foreground"
        onClick={addPage}
      >
        <Plus className="h-3 w-3" />
      </Button>
    </div>
  )
}
