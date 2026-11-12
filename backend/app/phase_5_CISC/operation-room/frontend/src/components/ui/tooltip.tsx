"use client"

import * as React from "react"
import * as TooltipPrimitive from "@radix-ui/react-tooltip"
import { cn } from '@operation-room/lib/utils'

// Temporary safety valve: Radix tooltips are triggering a compose-refs update loop
// in Studio V4. Disable them globally until the root cause is isolated. To re-enable,
// set NEXT_PUBLIC_ENABLE_RADIX_TOOLTIPS=true.
const enableRadixTooltips =
  typeof process !== 'undefined' && process.env.NEXT_PUBLIC_ENABLE_RADIX_TOOLTIPS === 'true'

const TooltipProviderPassthrough = ({ children }: { children: React.ReactNode }) => <>{children}</>
TooltipProviderPassthrough.displayName = 'TooltipProviderPassthrough'

const TooltipPassthrough = ({ children }: { children: React.ReactNode }) => <>{children}</>
TooltipPassthrough.displayName = 'TooltipPassthrough'

const TooltipTriggerPassthrough = ({ children }: { children: React.ReactNode }) => <>{children}</>
TooltipTriggerPassthrough.displayName = 'TooltipTriggerPassthrough'

const TooltipContentRadix = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(function TooltipContentRadix({ className, sideOffset = 4, ...props }, ref) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn(
          "z-50 overflow-hidden rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
          className
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  )
})

const TooltipContentFallback = React.forwardRef<HTMLElement, React.HTMLAttributes<HTMLElement>>(
  function TooltipContentFallback({ children }, _ref) {
    return <>{children}</>
  }
)

const TooltipProvider = enableRadixTooltips
  ? TooltipPrimitive.Provider
  : TooltipProviderPassthrough

const Tooltip = enableRadixTooltips
  ? TooltipPrimitive.Root
  : TooltipPassthrough

const TooltipTrigger = enableRadixTooltips
  ? TooltipPrimitive.Trigger
  : TooltipTriggerPassthrough

const TooltipContent = enableRadixTooltips
  ? TooltipContentRadix
  : TooltipContentFallback

TooltipContent.displayName = TooltipPrimitive.Content.displayName

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
