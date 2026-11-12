'use client'

import React from 'react'
import {
  Undo2,
  Redo2,
  Bold,
  Italic,
  Underline,
  Strikethrough,
  AlignLeft,
  AlignCenter,
  AlignRight,
  AlignJustify,
  List,
  ListOrdered,
  Quote,
  Code,
  Link2,
  Image as ImageIcon,
  Table,
  Minus,
  Plus,
  Type,
  Highlighter,
  ChevronDown,
  Sparkles,
  FileText,
  LayoutGrid,
} from 'lucide-react'
import { cn } from '@operation-room/lib/utils'
import { Button } from '@operation-room/components/ui/button'
import { Input } from '@operation-room/components/ui/input'
import { Separator } from '@operation-room/components/ui/separator'
import type { Editor } from '@tiptap/core'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@operation-room/components/ui/select'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@operation-room/components/ui/popover'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@operation-room/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@operation-room/components/ui/tooltip'
import { Toggle } from '@operation-room/components/ui/toggle'

// Color presets
const TEXT_COLORS = [
  { name: 'Default', value: '#1e293b' },
  { name: 'Red', value: '#dc2626' },
  { name: 'Orange', value: '#ea580c' },
  { name: 'Amber', value: '#d97706' },
  { name: 'Green', value: '#16a34a' },
  { name: 'Blue', value: '#2563eb' },
  { name: 'Purple', value: '#9333ea' },
  { name: 'Gray', value: '#64748b' },
]

const HIGHLIGHT_COLORS = [
  { name: 'None', value: 'transparent' },
  { name: 'Yellow', value: '#fef08a' },
  { name: 'Green', value: '#bbf7d0' },
  { name: 'Blue', value: '#bfdbfe' },
  { name: 'Purple', value: '#e9d5ff' },
  { name: 'Pink', value: '#fbcfe8' },
  { name: 'Orange', value: '#fed7aa' },
]

const FONT_FAMILIES = [
  { name: 'Geist', value: 'Geist' },
  { name: 'Geist Mono', value: 'Geist Mono' },
  { name: 'Inter', value: 'Inter' },
]

// Toolbar button component
interface ToolbarButtonProps {
  icon: React.ReactNode
  label: string
  shortcut?: string
  active?: boolean
  disabled?: boolean
  onClick?: () => void
}

const ToolbarButton = ({
  icon,
  label,
  shortcut,
  active,
  disabled,
  onClick,
}: ToolbarButtonProps) => (
  <Tooltip>
    <TooltipTrigger asChild>
      <Toggle
        pressed={active}
        onPressedChange={() => onClick?.()}
        disabled={disabled}
        size="sm"
        className={cn(
          "h-8 w-8 p-0",
          active && "bg-accent"
        )}
      >
        {icon}
      </Toggle>
    </TooltipTrigger>
    <TooltipContent side="bottom" className="flex items-center gap-2">
      <span>{label}</span>
      {shortcut && (
        <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
          {shortcut}
        </kbd>
      )}
    </TooltipContent>
  </Tooltip>
)

// Color picker component
interface ColorPickerProps {
  colors: Array<{ name: string; value: string }>
  value?: string
  onChange?: (color: string) => void
  label?: string
}

const ColorPicker = ({ colors, value, onChange, label }: ColorPickerProps) => (
  <div className="space-y-2">
    {label && <div className="text-xs font-medium text-muted-foreground">{label}</div>}
    <div className="grid grid-cols-4 gap-1">
      {colors.map((color) => (
        <button
          key={color.value}
          onClick={() => onChange?.(color.value)}
          className={cn(
            "w-7 h-7 rounded border-2 transition-all",
            value === color.value ? "border-primary scale-110" : "border-transparent hover:scale-105"
          )}
          style={{ backgroundColor: color.value === 'transparent' ? '#fff' : color.value }}
          title={color.name}
        >
          {color.value === 'transparent' && (
            <span className="text-xs text-muted-foreground">∅</span>
          )}
        </button>
      ))}
    </div>
  </div>
)

// Main toolbar component
interface CanvaToolbarProps {
  editor?: Editor | null
  onInsertComponent?: () => void
  onAIAssist?: () => void
  className?: string
}

export const CanvaToolbar = ({
  editor,
  onInsertComponent,
  onAIAssist,
  className,
}: CanvaToolbarProps) => {
  const [fontSize, setFontSize] = React.useState(12)
  const [fontFamily, setFontFamily] = React.useState('Geist')

  // Check if editor commands are available
  const canUndo = editor?.can().undo()
  const canRedo = editor?.can().redo()

  // Get current text formatting
  const isBold = editor?.isActive('bold')
  const isItalic = editor?.isActive('italic')
  const isUnderline = editor?.isActive('underline')
  const isStrike = editor?.isActive('strike')
  const isCode = editor?.isActive('code')
  const isBulletList = editor?.isActive('bulletList')
  const isOrderedList = editor?.isActive('orderedList')
  const isBlockquote = editor?.isActive('blockquote')

  // Alignment
  const isAlignLeft = editor?.isActive({ textAlign: 'left' })
  const isAlignCenter = editor?.isActive({ textAlign: 'center' })
  const isAlignRight = editor?.isActive({ textAlign: 'right' })
  const isAlignJustify = editor?.isActive({ textAlign: 'justify' })

  return (
    <div className={cn(
      "h-12 border-b flex items-center gap-1 px-2 bg-background overflow-x-auto",
      className
    )}>
      {/* Undo/Redo */}
      <div className="flex items-center gap-0.5">
        <ToolbarButton
          icon={<Undo2 className="h-4 w-4" />}
          label="Undo"
          shortcut="⌘Z"
          disabled={!canUndo}
          onClick={() => editor?.chain().focus().undo().run()}
        />
        <ToolbarButton
          icon={<Redo2 className="h-4 w-4" />}
          label="Redo"
          shortcut="⌘⇧Z"
          disabled={!canRedo}
          onClick={() => editor?.chain().focus().redo().run()}
        />
      </div>

      <Separator orientation="vertical" className="h-6 mx-1" />

      {/* Font Family */}
      <Select value={fontFamily} onValueChange={setFontFamily}>
        <SelectTrigger className="h-8 w-36 font-ui text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {FONT_FAMILIES.map((font) => (
            <SelectItem key={font.value} value={font.value}>
              <span style={{ fontFamily: font.value }}>{font.name}</span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Font Size */}
      <div className="flex items-center gap-0.5">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-6"
          onClick={() => setFontSize(Math.max(8, fontSize - 1))}
        >
          <Minus className="h-3 w-3" />
        </Button>
        <Input
          type="number"
          value={fontSize}
          onChange={(e) => setFontSize(Number(e.target.value))}
          className="w-12 h-8 text-center text-xs px-1"
          min={8}
          max={72}
        />
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-6"
          onClick={() => setFontSize(Math.min(72, fontSize + 1))}
        >
          <Plus className="h-3 w-3" />
        </Button>
      </div>

      <Separator orientation="vertical" className="h-6 mx-1" />

      {/* Text Color */}
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <div className="flex flex-col items-center">
              <Type className="h-4 w-4" />
              <div className="w-4 h-1 mt-0.5 rounded-sm bg-foreground" />
            </div>
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-44 p-3" align="start">
          <ColorPicker
            colors={TEXT_COLORS}
            label="Text Color"
            onChange={(color) => editor?.chain().focus().setColor(color).run()}
          />
        </PopoverContent>
      </Popover>

      {/* Highlight Color */}
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <Highlighter className="h-4 w-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-44 p-3" align="start">
          <ColorPicker
            colors={HIGHLIGHT_COLORS}
            label="Highlight"
            onChange={(color) => editor?.chain().focus().toggleHighlight({ color }).run()}
          />
        </PopoverContent>
      </Popover>

      <Separator orientation="vertical" className="h-6 mx-1" />

      {/* Text Formatting */}
      <div className="flex items-center gap-0.5">
        <ToolbarButton
          icon={<Bold className="h-4 w-4" />}
          label="Bold"
          shortcut="⌘B"
          active={isBold}
          onClick={() => editor?.chain().focus().toggleBold().run()}
        />
        <ToolbarButton
          icon={<Italic className="h-4 w-4" />}
          label="Italic"
          shortcut="⌘I"
          active={isItalic}
          onClick={() => editor?.chain().focus().toggleItalic().run()}
        />
        <ToolbarButton
          icon={<Underline className="h-4 w-4" />}
          label="Underline"
          shortcut="⌘U"
          active={isUnderline}
          onClick={() => editor?.chain().focus().toggleUnderline().run()}
        />
        <ToolbarButton
          icon={<Strikethrough className="h-4 w-4" />}
          label="Strikethrough"
          active={isStrike}
          onClick={() => editor?.chain().focus().toggleStrike().run()}
        />
      </div>

      <Separator orientation="vertical" className="h-6 mx-1" />

      {/* Alignment */}
      <div className="flex items-center gap-0.5">
        <ToolbarButton
          icon={<AlignLeft className="h-4 w-4" />}
          label="Align Left"
          active={isAlignLeft}
          onClick={() => editor?.chain().focus().setTextAlign('left').run()}
        />
        <ToolbarButton
          icon={<AlignCenter className="h-4 w-4" />}
          label="Align Center"
          active={isAlignCenter}
          onClick={() => editor?.chain().focus().setTextAlign('center').run()}
        />
        <ToolbarButton
          icon={<AlignRight className="h-4 w-4" />}
          label="Align Right"
          active={isAlignRight}
          onClick={() => editor?.chain().focus().setTextAlign('right').run()}
        />
        <ToolbarButton
          icon={<AlignJustify className="h-4 w-4" />}
          label="Justify"
          active={isAlignJustify}
          onClick={() => editor?.chain().focus().setTextAlign('justify').run()}
        />
      </div>

      <Separator orientation="vertical" className="h-6 mx-1" />

      {/* Lists */}
      <div className="flex items-center gap-0.5">
        <ToolbarButton
          icon={<List className="h-4 w-4" />}
          label="Bullet List"
          active={isBulletList}
          onClick={() => editor?.chain().focus().toggleBulletList().run()}
        />
        <ToolbarButton
          icon={<ListOrdered className="h-4 w-4" />}
          label="Numbered List"
          active={isOrderedList}
          onClick={() => editor?.chain().focus().toggleOrderedList().run()}
        />
      </div>

      <Separator orientation="vertical" className="h-6 mx-1" />

      {/* Block Elements */}
      <div className="flex items-center gap-0.5">
        <ToolbarButton
          icon={<Quote className="h-4 w-4" />}
          label="Quote"
          active={isBlockquote}
          onClick={() => editor?.chain().focus().toggleBlockquote().run()}
        />
        <ToolbarButton
          icon={<Code className="h-4 w-4" />}
          label="Code"
          active={isCode}
          onClick={() => editor?.chain().focus().toggleCode().run()}
        />
      </div>

      <div className="flex-1" />

      {/* Insert Menu */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 gap-1.5">
            <Plus className="h-4 w-4" />
            Insert
            <ChevronDown className="h-3 w-3 opacity-50" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuItem onClick={onInsertComponent}>
            <LayoutGrid className="h-4 w-4 mr-2" />
            Module Component
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => editor?.chain().focus().insertTable({ rows: 3, cols: 3 }).run()}>
            <Table className="h-4 w-4 mr-2" />
            Table
          </DropdownMenuItem>
          <DropdownMenuItem>
            <ImageIcon className="h-4 w-4 mr-2" />
            Image
          </DropdownMenuItem>
          <DropdownMenuItem>
            <Link2 className="h-4 w-4 mr-2" />
            Link
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem>
            <FileText className="h-4 w-4 mr-2" />
            Page Break
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* AI Assist Button */}
      <Button
        variant="default"
        size="sm"
        className="h-8 gap-1.5 bg-gradient-to-r from-sky-500 to-indigo-500 font-ui hover:from-sky-600 hover:to-indigo-600"
        onClick={onAIAssist}
      >
        <Sparkles className="h-4 w-4" />
        AI Assist
      </Button>
    </div>
  )
}
