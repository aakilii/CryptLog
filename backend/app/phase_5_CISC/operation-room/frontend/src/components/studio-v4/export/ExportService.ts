import { CanvasElement, PageMeta } from '../store/useStudioStore'

export const executeRegexMask = (payload: any): any => {
  if (!payload) return payload;
  const payloadStr = JSON.stringify(payload);
  
  // Scrubber: IPv4 Addresses
  const ipMask = payloadStr.replace(/\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b/g, '[REDACTED_IP]');

  // Scrubber: MAC Addresses
  const macMask = ipMask.replace(/\b(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})\b/g, '[REDACTED_MAC]');
  // Return sterile parsed JSON
  return JSON.parse(macMask);
}

