export const EVIDENCE_NAVIGATE_EVENT = 'evidence:navigate'

const DEFAULT_DRILL_PATH = ['finding', 'evidence', 'anchor']

export interface InvestigatorDrillTarget {
    sourcePanel: string
    title: string
    summary?: string
    questionType?: string
    visualPattern?: string
    drillPath: string[]
    findingRef?: string
    evidenceRef?: string
    anchorRef?: string
    module?: string
    confidence?: number
    timestamp: string
}

export interface PanelFindingPayload {
    title: string
    content: string
    source: string
    severity?: 'critical' | 'high' | 'medium' | 'low' | 'info'
    evidenceIds?: string[]
    confidence?: number
    questionType?: string
    visualPattern?: string
    tracePath?: string[]
    anchorRef?: string
}

const asString = (value: unknown): string | undefined => {
    if (typeof value !== 'string') return undefined
    const trimmed = value.trim()
    return trimmed.length > 0 ? trimmed : undefined
}

const asNumber = (value: unknown): number | undefined => {
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value
    }
    if (typeof value === 'string' && value.trim().length > 0) {
        const parsed = Number(value)
        if (Number.isFinite(parsed)) {
            return parsed
        }
    }
    return undefined
}

const asDrillPath = (value: unknown): string[] => {
    if (!Array.isArray(value)) {
        return [...DEFAULT_DRILL_PATH]
    }
    const steps = value
        .map((step) => asString(step))
        .filter((step): step is string => Boolean(step))
    return steps.length > 0 ? steps : [...DEFAULT_DRILL_PATH]
}

const buildDrillTarget = (value: Record<string, unknown>): InvestigatorDrillTarget => {
    const sourcePanel = asString(value.sourcePanel)
        || asString(value.source)
        || asString(value.module)
        || 'investigation'
    const evidenceRef = asString(value.evidenceRef)
        || asString(value.refId)
        || asString(value.citationId)
        || asString(value.hash)
        || asString(value.id)
    const findingRef = asString(value.findingRef)
        || asString(value.hypothesisId)
        || evidenceRef
    const anchorRef = asString(value.anchorRef)
        || asString(value.anchorId)
        || asString(value.tl_event_id)
    const title = asString(value.title)
        || (evidenceRef ? `Evidence ${evidenceRef}` : 'Evidence Drill Path')
    const summary = asString(value.summary)
        || asString(value.message)
        || asString(value.description)

    return {
        sourcePanel,
        title,
        summary,
        questionType: asString(value.questionType),
        visualPattern: asString(value.visualPattern),
        drillPath: asDrillPath(value.drillPath),
        findingRef,
        evidenceRef,
        anchorRef,
        module: asString(value.module) || sourcePanel,
        confidence: asNumber(value.confidence),
        timestamp: asString(value.timestamp) || new Date().toISOString(),
    }
}

export const normalizeEvidenceDrillTarget = (detail: unknown): InvestigatorDrillTarget | null => {
    if (!detail || typeof detail !== 'object') {
        return null
    }

    const payload = detail as Record<string, unknown>
    const drill = payload.drill
    if (drill && typeof drill === 'object') {
        return buildDrillTarget(drill as Record<string, unknown>)
    }

    return buildDrillTarget(payload)
}

export const emitEvidenceDrill = (
    target: Omit<InvestigatorDrillTarget, 'drillPath' | 'timestamp'> & {
        drillPath?: string[]
        timestamp?: string
    }
) => {
    if (typeof window === 'undefined') {
        return
    }

    const drill: InvestigatorDrillTarget = {
        ...target,
        drillPath: asDrillPath(target.drillPath),
        timestamp: target.timestamp || new Date().toISOString(),
    }

    window.dispatchEvent(
        new CustomEvent(EVIDENCE_NAVIGATE_EVENT, {
            detail: { drill },
        })
    )
}

export const drillTargetMatchesText = (
    target: InvestigatorDrillTarget | null,
    textValue?: string | null
) => {
    if (!target || !textValue) {
        return false
    }

    const haystack = textValue.toLowerCase()
    const candidates = [
        target.evidenceRef,
        target.anchorRef,
        target.findingRef,
        target.title,
    ]

    return candidates
        .filter((value): value is string => Boolean(value))
        .some((value) => haystack.includes(value.toLowerCase()))
}
