/** Normalize canvas element `.data` for EvidenceContent (print + preview). */

export function getComponentPayload(data: Record<string, unknown> | undefined): unknown {
  if (!data) return undefined
  if (data.data !== undefined) return data.data
  if (data.payload !== undefined) return data.payload
  return data
}

export function getComponentDataType(data: Record<string, unknown> | undefined): string {
  if (!data) return 'chart'
  const type = data.type
  if (typeof type === 'string' && type.length > 0) return type
  const componentId = data.componentId
  if (typeof componentId === 'string' && componentId.length > 0) return componentId
  return 'chart'
}
