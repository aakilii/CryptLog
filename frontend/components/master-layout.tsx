import React from "react"
import { AppSidebar } from "./app-sidebar"
import { TopNavbar } from "./top-navbar"
import { SidebarProvider } from "./ui/sidebar"

export function MasterLayout({ children }: { children: React.ReactNode }) {
  const new_ = children

  return (
    <SidebarProvider>
      <div className="flex h-screen w-full bg-[#fafaf9] overflow-hidden m-0 p-0 border-none">
        <AppSidebar className="shrink-0 border-r border-slate-200 z-50 m-0 p-0 rounded-none" />
        <div className="flex flex-1 flex-col min-w-0 h-full m-0 p-0 border-none bg-transparent rounded-none">
          <TopNavbar className="m-0 rounded-none w-full border-x-0 border-t-0" />
          <main className="flex-1 overflow-y-auto overflow-x-hidden p-6 md:p-8 m-0">
            {new_}
          </main>
        </div>
      </div>
    </SidebarProvider>
  )
}