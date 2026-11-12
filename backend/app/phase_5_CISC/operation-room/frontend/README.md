# NFLIP Frontend — Next.js 14 Application

Enterprise-grade frontend for the NFLIP forensic investigation platform.

## Technology Stack

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript + JavaScript (migration in progress)
- **Styling:** Tailwind CSS + shadcn/ui
- **State Management:** Zustand
- **Rich Text:** TipTap
- **Visualization:** Recharts, Vega-Lite

## Directory Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── (main)/             # Main case management routes
│   │   │   ├── cases/          # Case list, detail, modules
│   │   │   │   ├── [id]/       # Case-specific pages
│   │   │   │   │   ├── anomalies/
│   │   │   │   │   ├── chain-of-custody/
│   │   │   │   │   ├── correlation/
│   │   │   │   │   ├── crud/
│   │   │   │   │   ├── depth/
│   │   │   │   │   ├── import/
│   │   │   │   │   ├── network/
│   │   │   │   │   └── timeline/
│   │   │   │   └── new/        # Create new case
│   │   │   └── page.js         # Dashboard
│   │   └── (studio)/           # Report Studio routes
│   │       └── cases/[id]/studio-v4/
│   │
│   ├── components/             # React components
│   │   ├── ai-panel/           # AI assistant sidebar (14 files)
│   │   ├── charts/             # Visualization components (5 files)
│   │   ├── common/             # Shared components (1 file)
│   │   ├── deep-research/      # Research UI (8 files)
│   │   ├── evidence/           # Evidence management (1 file)
│   │   ├── forensic/           # Forensic-specific UI (1 file)
│   │   ├── icons/              # Icon components (1 file)
│   │   ├── studio-v4/          # Report Studio canvas (48 files)
│   │   │   ├── canvas/         # Canvas rendering
│   │   │   ├── panels/         # Inspector panels
│   │   │   ├── dialogs/        # Modal dialogs
│   │   │   ├── toolbar/        # Toolbar components
│   │   │   └── ...
│   │   ├── tiptap/             # Rich text editor (4 files)
│   │   └── ui/                 # shadcn/ui components (22 files)
│   │
│   ├── hooks/                  # React hooks
│   │   ├── useInvestigationStream.ts
│   │   └── useWebSocket.ts
│   │
│   ├── lib/                    # Utility libraries
│   │   ├── api.js              # API client
│   │   ├── utils.ts            # Tailwind utilities
│   │   ├── templates.ts        # Report templates
│   │   └── ...
│   │
│   ├── stores/                 # Zustand state management
│   │   └── investigationStore.ts
│   │
│   ├── context/                # React Context providers
│   │   └── FilterStateProvider.tsx
│   │
│   └── types/                  # TypeScript type definitions
│
├── public/                     # Static assets
│   └── templates/              # Report template images
│
├── scripts/                    # Build scripts
│   └── dev-safe.mjs
│
├── .eslintrc.json              # ESLint configuration
├── components.json             # shadcn/ui configuration
├── next.config.mjs             # Next.js configuration
├── package.json                # Dependencies
├── postcss.config.js           # PostCSS configuration
├── tailwind.config.js          # Tailwind CSS configuration
└── tsconfig.json               # TypeScript configuration
```

## Key Features

### 1. Report Studio V4 (Canvas-Based Editing)
- Drag-and-drop report builder with absolute positioning
- Live chart integration from backend SQL queries
- PDF export via ReportLab (backend-rendered)
- Multi-page A4 layout with pixel-perfect print preview

### 2. Investigation Dashboard
- Real-time case overview
- Module status tracking (Timeline, Anomaly, Correlation, etc.)
- Quick access to all analysis views

### 3. Module Views
Each forensic module has a dedicated view:
- **Timeline:** Event reconstruction with filters
- **Anomaly:** ML-detected anomalies with SHAP explanations
- **Correlation:** Entity relationship graphs
- **CRUD:** Database operation analysis
- **Network:** Network flow visualization
- **Depth:** Impact assessment across 4 dimensions
- **Chain of Custody:** Immutable audit trail

### 4. Deep Research Panel
- AI-powered investigation assistant
- Thought tree visualization
- Human-in-the-loop clarifications
- Plan-based research execution

## Development

### Install Dependencies
```bash
npm install
```

### Run Development Server
```bash
npm run dev
```

Access at: http://localhost:3000

### Build for Production
```bash
npm run build
npm start
```

### Type Checking
```bash
npx tsc --noEmit
```

## Code Quality

- **TypeScript:** 92 .tsx files, 18 .ts files (110 total)
- **JavaScript:** 31 .js files (migration to TS recommended)
- **Linting:** ESLint configured for Next.js + React
- **Formatting:** Tailwind class sorting

## Migration Notes

The codebase is transitioning from JavaScript to TypeScript:
- All new files should be `.tsx` or `.ts`
- Existing `.js` files in `app/` and `components/` should be gradually migrated
- Priority: app route pages → component files → utilities

## Configuration

### Environment Variables
Create `.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Tailwind Theme
Custom forensic theme with dark navy backgrounds, glassmorphism, and severity-based color coding:
- Critical: Rose
- High: Orange
- Medium: Yellow
- Low: Blue
- Info: Cyan

## License

Proprietary — CISC Internal Use Only
