'use client';

/**
 * Report Preview Panel
 * 
 * Full-screen preview of the report before final export.
 * Shows all pages rendered in print layout with:
 * - Page-by-page navigation
 * - Zoom controls
 * - Edit mode toggle (for quick fixes)
 * - Export confirmation
 */

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Edit,
  Eye,
  FileDown,
  FileText,
  Maximize2,
  Minimize2,
  X,
  ZoomIn,
  ZoomOut
} from 'lucide-react';
import NextImage from 'next/image';
import { useCallback, useEffect, useState } from 'react';
import { CanvasElement, PageMeta, useStudioStore } from '../store/useStudioStore';

// Page dimensions (A4 at 96 DPI)
const PAGE_WIDTH = 794; // 210mm
const PAGE_HEIGHT = 1123; // 297mm

interface PreviewPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onExport: (format: 'pdf' | 'docx') => void;
  caseId: string;
}

// Simplified element renderer for preview
const PreviewElement = ({ element }: { element: CanvasElement }) => {
  const scale = 0.5; // Preview scale

  if (element.type === 'text') {
    return (
      <div
        className="absolute bg-white border border-gray-200 rounded p-2 overflow-hidden"
        style={{
          left: element.x * scale,
          top: element.y * scale,
          width: element.width * scale,
          height: element.height * scale,
          fontSize: 10 * scale,
        }}
      >
        <div className="text-gray-800 whitespace-pre-wrap">
          {element.data.content || 'Text content'}
        </div>
      </div>
    );
  }

  if (element.type === 'component') {
    return (
      <div
        className="absolute bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded overflow-hidden"
        style={{
          left: element.x * scale,
          top: element.y * scale,
          width: element.width * scale,
          height: element.height * scale,
        }}
      >
        <div className="p-1 text-[8px] text-blue-600 font-medium truncate">
          {element.data.componentId || element.data.type || 'Component'}
        </div>
        <div className="flex-1 flex items-center justify-center text-blue-400">
          <FileText className="w-6 h-6 opacity-30" />
        </div>
      </div>
    );
  }

  if (element.type === 'image') {
    return (
      <div
        className="absolute bg-gray-100 border border-gray-200 rounded overflow-hidden"
        style={{
          left: element.x * scale,
          top: element.y * scale,
          width: element.width * scale,
          height: element.height * scale,
        }}
      >
        {element.data.url ? (
          <NextImage
            src={element.data.url}
            alt={element.data.name || 'Image'}
            width={Math.max(1, Math.round(element.width * scale))}
            height={Math.max(1, Math.round(element.height * scale))}
            unoptimized
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            <FileText className="w-6 h-6" />
          </div>
        )}
      </div>
    );
  }

  // Shape/default
  return (
    <div
      className="absolute bg-gray-200 border border-gray-300 rounded"
      style={{
        left: element.x * scale,
        top: element.y * scale,
        width: element.width * scale,
        height: element.height * scale,
      }}
    />
  );
};

// Single page preview
const PagePreview = ({
  page,
  pageNumber,
  isActive,
  onClick
}: {
  page: PageMeta;
  pageNumber: number;
  isActive: boolean;
  onClick: () => void;
}) => {
  const scale = 0.5;

  return (
    <div
      className={cn(
        "relative cursor-pointer transition-all duration-200",
        "shadow-lg hover:shadow-xl",
        isActive && "ring-2 ring-blue-500 ring-offset-2"
      )}
      style={{
        width: PAGE_WIDTH * scale,
        height: PAGE_HEIGHT * scale,
      }}
      onClick={onClick}
    >
      {/* Page background */}
      <div className="absolute inset-0 bg-white rounded">
        {/* Elements */}
        {page.elements.map((element) => (
          <PreviewElement key={element.id} element={element} />
        ))}
      </div>

      {/* Page number badge */}
      <div className="absolute bottom-2 right-2 px-2 py-0.5 bg-gray-800/80 text-white text-xs rounded">
        {pageNumber}
      </div>
    </div>
  );
};

export function ReportPreviewPanel({
  open,
  onOpenChange,
  onExport,
  caseId,
}: PreviewPanelProps) {
  const pages = useStudioStore((state) => state.pages);
  const focusMode = useStudioStore((state) => state.focusMode);
  const documentTitle = useStudioStore((state) => state.documentTitle);

  const [currentPage, setCurrentPage] = useState(0);
  const [zoom, setZoom] = useState(100);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [validationIssues, setValidationIssues] = useState<string[]>([]);

  // Validation check
  useEffect(() => {
    if (!open) return;

    const issues: string[] = [];

    // Check for empty pages
    pages.forEach((page, idx) => {
      if (page.elements.length === 0) {
        issues.push(`Page ${idx + 1} is empty`);
      }
    });

    // Check for unverified elements
    let unverifiedCount = 0;
    pages.forEach(page => {
      page.elements.forEach(el => {
        if (el.isOriginal === false) {
          unverifiedCount++;
        }
      });
    });
    if (unverifiedCount > 0) {
      issues.push(`${unverifiedCount} element(s) have modified content (Chain of Custody broken)`);
    }

    setValidationIssues(issues);
  }, [open, pages]);

  // Navigate pages
  const prevPage = useCallback(() => {
    setCurrentPage(p => Math.max(0, p - 1));
  }, []);

  const nextPage = useCallback(() => {
    setCurrentPage(p => Math.min(pages.length - 1, p + 1));
  }, [pages.length]);

  // Keyboard navigation
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') prevPage();
      if (e.key === 'ArrowRight') nextPage();
      if (e.key === 'Escape') onOpenChange(false);
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, prevPage, nextPage, onOpenChange]);

  const handleExportPDF = useCallback(() => {
    onExport('pdf');
    onOpenChange(false);
  }, [onExport, onOpenChange]);

  const handleExportDOCX = useCallback(() => {
    onExport('docx');
    onOpenChange(false);
  }, [onExport, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={cn(
        "max-w-[95vw] max-h-[95vh] w-[1400px] h-[900px] p-0 flex flex-col",
        isFullscreen && "w-screen h-screen max-w-screen max-h-screen rounded-none"
      )}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b bg-slate-50">
          <div className="flex items-center gap-3">
            <Eye className="w-5 h-5 text-blue-500" />
            <div>
              <h2 className="font-semibold text-slate-900">{documentTitle}</h2>
              <p className="text-xs text-slate-500">
                {pages.length} page{pages.length !== 1 ? 's' : ''} • {focusMode} Mode
              </p>
            </div>
          </div>

          {/* Zoom controls */}
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={() => setZoom(z => Math.max(50, z - 10))}>
              <ZoomOut className="w-4 h-4" />
            </Button>
            <span className="text-sm text-slate-600 w-12 text-center">{zoom}%</span>
            <Button variant="ghost" size="icon" onClick={() => setZoom(z => Math.min(200, z + 10))}>
              <ZoomIn className="w-4 h-4" />
            </Button>
            <div className="w-px h-6 bg-slate-200 mx-2" />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsFullscreen(!isFullscreen)}
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </Button>
          </div>
        </div>

        {/* Main content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Page thumbnails sidebar */}
          <div className="w-48 border-r bg-slate-100 overflow-y-auto p-3 space-y-3">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide px-1">Pages</p>
            {pages.map((page, idx) => (
              <div
                key={page.id}
                className={cn(
                  "cursor-pointer rounded-lg overflow-hidden transition-all",
                  "hover:ring-2 hover:ring-blue-300",
                  currentPage === idx && "ring-2 ring-blue-500"
                )}
                onClick={() => setCurrentPage(idx)}
              >
                <div className="bg-white aspect-[210/297] relative shadow-sm">
                  <div className="absolute inset-0 p-1">
                    {page.elements.slice(0, 5).map((el, i) => (
                      <div
                        key={el.id}
                        className="bg-slate-200 rounded-sm mb-0.5"
                        style={{ height: '12%', opacity: 0.5 + (i * 0.1) }}
                      />
                    ))}
                  </div>
                  <div className="absolute bottom-1 right-1 text-[10px] bg-slate-800/70 text-white px-1.5 rounded">
                    {idx + 1}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Main preview area */}
          <div className="flex-1 bg-slate-200 overflow-auto flex items-center justify-center p-8">
            <div
              className="bg-white shadow-2xl rounded-lg overflow-hidden transition-transform"
              style={{
                width: PAGE_WIDTH * (zoom / 100),
                height: PAGE_HEIGHT * (zoom / 100),
                transform: `scale(1)`,
              }}
            >
              {pages[currentPage] && (
                <div className="relative w-full h-full">
                  {pages[currentPage].elements.map((element) => (
                    <div
                      key={element.id}
                      className="absolute"
                      style={{
                        left: element.x * (zoom / 100),
                        top: element.y * (zoom / 100),
                        width: element.width * (zoom / 100),
                        height: element.height * (zoom / 100),
                      }}
                    >
                      {element.type === 'text' && (
                        <div className="w-full h-full p-2 overflow-hidden text-sm">
                          {element.data.content}
                        </div>
                      )}
                      {element.type === 'component' && (
                        <div className="w-full h-full bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 rounded flex items-center justify-center">
                          <span className="text-blue-400 text-sm">
                            {element.data.componentId || element.data.type}
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Validation sidebar */}
          <div className="w-64 border-l bg-white overflow-y-auto">
            <div className="p-4 space-y-4">
              <div>
                <h3 className="font-medium text-slate-900 mb-2 flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-500" />
                  Export Checklist
                </h3>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    <div className={cn(
                      "w-4 h-4 rounded-full flex items-center justify-center",
                      pages.length > 0 ? "bg-green-100" : "bg-red-100"
                    )}>
                      {pages.length > 0 ? (
                        <Check className="w-3 h-3 text-green-600" />
                      ) : (
                        <X className="w-3 h-3 text-red-600" />
                      )}
                    </div>
                    <span className="text-slate-600">Has content</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <div className="w-4 h-4 rounded-full flex items-center justify-center bg-green-100">
                      <Check className="w-3 h-3 text-green-600" />
                    </div>
                    <span className="text-slate-600">Focus mode set</span>
                  </div>
                </div>
              </div>

              {validationIssues.length > 0 && (
                <div>
                  <h3 className="font-medium text-amber-700 mb-2 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    Warnings
                  </h3>
                  <div className="space-y-1">
                    {validationIssues.map((issue, idx) => (
                      <p key={idx} className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded">
                        {issue}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              <div className="pt-4 border-t">
                <h3 className="font-medium text-slate-900 mb-2">Export Options</h3>
                <div className="space-y-2">
                  <Badge variant="outline" className="text-xs">
                    Case: {caseId}
                  </Badge>
                  <Badge variant="outline" className="text-xs">
                    Mode: {focusMode}
                  </Badge>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t bg-slate-50">
          {/* Page navigation */}
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={prevPage} disabled={currentPage === 0}>
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-sm text-slate-600 min-w-[80px] text-center">
              Page {currentPage + 1} of {pages.length}
            </span>
            <Button variant="outline" size="sm" onClick={nextPage} disabled={currentPage === pages.length - 1}>
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              <Edit className="w-4 h-4 mr-2" />
              Continue Editing
            </Button>
            <Button
              className="bg-blue-600 hover:bg-blue-700 text-white"
              onClick={handleExportPDF}
              disabled={validationIssues.length > 0}
            >
              <FileDown className="w-4 h-4 mr-2" />
              Export PDF
            </Button>
            <Button
              variant="outline"
              onClick={handleExportDOCX}
              disabled={validationIssues.length > 0}
            >
              <FileText className="w-4 h-4 mr-2" />
              Export DOCX
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default ReportPreviewPanel;
