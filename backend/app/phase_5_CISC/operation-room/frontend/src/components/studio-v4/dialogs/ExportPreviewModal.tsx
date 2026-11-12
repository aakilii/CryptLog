import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@operation-room/components/ui/dialog';
import { Button } from '@operation-room/components/ui/button';
import { Eye, AlertTriangle } from 'lucide-react';
import { useStudioStore } from '../store/useStudioStore';

interface ExportPreviewModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (engine: 'standard' | 'dynamite') => void;
}

export function ExportPreviewModal({ open, onOpenChange, onConfirm }: ExportPreviewModalProps) {
  const focusMode = useStudioStore((s) => s.focusMode);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {focusMode === 'Evidence' ? <AlertTriangle className="text-red-500 h-5 w-5" /> : <Eye className="text-sky-500 h-5 w-5" />}
            Export Mode Preview
          </DialogTitle>
        </DialogHeader>

        <div className="my-4 space-y-4">
          <div className="bg-slate-100 p-4 rounded-md border border-slate-200">
            <h3 className="font-semibold flex items-center gap-2 mb-4 text-slate-800 border-b border-slate-300 pb-2">
              Current Mode: <span className="uppercase text-sky-600">{focusMode}</span>
            </h3>
            
            {focusMode === 'Evidence' && (
              <p className="text-sm text-red-600 font-medium">
                Exporting in Evidence Mode is FORBIDDEN. It contains deeply nested cryptographic details and internal DuckDB queries meant only for internal auditors. Please switch your view to a different mode to export.
              </p>
            )}

            {focusMode === 'Story' && (
              <div className="text-sm text-slate-600 space-y-2">
                <p><strong>Executive Tier Export.</strong> Facts are curated for the Executive Suite before reaching the Ghost Editor:</p>
                <p>• Data points with <strong>≥ 80% Confidence</strong> are retained.</p>
                <p className="text-emerald-600 font-medium">• Unverified telemetry (formerly incorrectly hardcoded to 100%) is now safely hidden from the story.</p>
                <p>• Heavy technical IPs and hashes will be obfuscated visually.</p>
              </div>
            )}

            {focusMode === 'Review' && (
              <div className="text-sm text-slate-600 space-y-2">
                <p><strong>Internal Analyst Export.</strong> You are exporting the raw workspace.</p>
                <p>• All claims (Draft, Disputed, Approved) are retained for external review.</p>
                <p>• All graphs and telemetry data persist at their original confidence tiers.</p>
              </div>
            )}

            {focusMode === 'Redact' && (
              <div className="text-sm text-slate-600 space-y-2">
                <p><strong>Legal Scrub Export.</strong> The document will be fully sanitized.</p>
                <p>• MAC addresses, IPv4s, and target identifiers will be hard-replaced with `[REDACTED]` prior to compiling the final payload.</p>
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="flex sm:flex-row flex-col justify-between gap-2 mt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          {focusMode !== 'Evidence' && (
            <div className="flex sm:flex-row flex-col gap-2">
              <Button
                variant="outline"
                className="border-sky-600 text-sky-600 hover:bg-sky-50 whitespace-nowrap"
                onClick={() => {
                  onOpenChange(false);
                  onConfirm('standard');
                }}
              >
                Standard Export
              </Button>
              <Button
                className="bg-[rgb(3,7,18)] hover:bg-[rgb(3,7,18)]/90 text-white whitespace-nowrap"
                onClick={() => {
                  onOpenChange(false);
                  onConfirm('dynamite');
                }}
              >
                Formal Dynamite Report
              </Button>
            </div>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}