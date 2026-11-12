"use client"

import { TooltipProvider } from '@operation-room/components/ui/tooltip';

export default function StudioLayout({ children }) {
	return (
		<TooltipProvider>{children}</TooltipProvider>
	);
}