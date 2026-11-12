'use client'

import { Button } from '@/components/ui/button'
import {
  FolderOpen,
  Image as ImageIcon,
  MoreVertical,
  UploadCloud
} from 'lucide-react'
import NextImage from 'next/image'
import { useState } from 'react'
import {
  PanelContent,
} from '../ExpandablePanel'

const MOCK_UPLOADS = [
  { id: 'up-1', name: 'Company_Logo.png', type: 'image', url: '/api/placeholder/logo.svg' },
  { id: 'up-2', name: 'Suspect_Phone.jpg', type: 'image', url: '/api/placeholder/phone.svg' },
  { id: 'up-3', name: 'Network_Diagram.pdf', type: 'document', url: '/api/placeholder/doc.svg' },
]

interface UploadsPanelProps {
  onInsertUpload?: (upload: any) => void
}

export const UploadsPanel = ({ onInsertUpload }: UploadsPanelProps) => {
  const [uploads] = useState(MOCK_UPLOADS)

  return (
    <div className="flex flex-col h-full overflow-hidden bg-muted/10">
      <PanelContent className="p-4 space-y-6">

        {/* Upload Action */}
        <div className="w-full">
          <Button className="w-full h-12 bg-primary text-primary-foreground font-geist shadow-sm hover:shadow-md transition-all gap-2">
            <UploadCloud className="w-5 h-5" />
            Upload files
          </Button>
          <div className="mt-3 flex items-center gap-2">
            <Button variant="outline" size="sm" className="flex-1 h-8 text-xs font-ui bg-background">
              <ImageIcon className="w-3 h-3 mr-1" /> Images
            </Button>
            <Button variant="outline" size="sm" className="flex-1 h-8 text-xs font-ui bg-background">
              <FolderOpen className="w-3 h-3 mr-1" /> Documents
            </Button>
          </div>
        </div>

        {/* Uploads Grid */}
        <div className="grid grid-cols-2 gap-2">
          {uploads.map((file) => (
            <div
              key={file.id}
              className="group relative aspect-square rounded-lg border bg-card overflow-hidden cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => onInsertUpload?.(file)}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('application/json', JSON.stringify({
                  type: 'upload',
                  fileId: file.id,
                  url: file.url
                }))
              }}
            >
              <NextImage
                src={file.url}
                alt={file.name}
                fill
                unoptimized
                sizes="(max-width: 768px) 50vw, 25vw"
                className="w-full h-full object-cover opacity-70 group-hover:opacity-100 transition-opacity"
              />
              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-2 translate-y-full group-hover:translate-y-0 transition-transform">
                <span className="text-[10px] text-white font-ui font-medium truncate block">{file.name}</span>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="absolute top-1 right-1 h-6 w-6 opacity-0 group-hover:opacity-100 bg-black/40 hover:bg-black/60 text-white rounded-full transition-all"
              >
                <MoreVertical className="w-3 h-3" />
              </Button>
            </div>
          ))}
        </div>

      </PanelContent>
    </div>
  )
}
