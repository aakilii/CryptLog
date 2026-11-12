import { CanvasElement } from '@operation-room/components/studio-v4/store/useStudioStore'

// Helper macro to generate generic element skeletons for template layouts
const t = (
  id: string,
  type: CanvasElement['type'],
  x: number,
  y: number,
  w: number,
  h: number,
  data: any
): CanvasElement => ({
  id,
  type,
  x,
  y,
  width: w,
  height: h,
  zIndex: 1,
  data
})

export const MASTER_TEMPLATES: Record<string, CanvasElement[]> = {
  'ransomware-post-mortem': [
    t('rt-1', 'text', 20, 20, 600, 60, { textType: 'heading', style: 'heading', content: 'RANSOMWARE POST-MORTEM' }),
    t('rt-2', 'text', 20, 80, 600, 40, { textType: 'paragraph', style: 'paragraph', content: 'EXECUTIVE SUMMARY\nDetails regarding encryption phases and IOCs.' }),
    t('rt-3', 'component', 20, 130, 280, 250, { type: 'chart', chartType: 'timeline', source: 'timeline', title: 'Encryption Timeline' }),
    t('rt-4', 'component', 320, 130, 300, 250, { type: 'anomaly', source: 'anomaly', title: 'File System Spikes' }),
    t('rt-5', 'text', 20, 390, 600, 100, { textType: 'paragraph', style: 'paragraph', content: 'RECOMMENDATIONS\n1. Re-image affected hosts...\n2. Block hash C2s.' })
  ],
  'insider-threat-exfil': [
    t('it-1', 'text', 20, 20, 600, 60, { textType: 'heading', style: 'heading', content: 'INSIDER THREAT EXFILTRATION' }),
    t('it-2', 'component', 20, 90, 600, 350, { type: 'network-flow', source: 'network', title: 'Unusual Outbound Density' }),
    t('it-3', 'component', 20, 450, 290, 200, { type: 'chart', source: 'timeline', title: 'Off-hours Authentications' }),
    t('it-4', 'text', 330, 450, 290, 200, { textType: 'paragraph', style: 'paragraph', content: 'INVESTIGATOR NOTES\nMassive data egress to external IP observed concurrently with abnormal USB mounting.' })
  ],
  'cloud-breach-exec': [
    t('cb-1', 'text', 20, 20, 600, 60, { textType: 'heading', style: 'heading', content: 'CLOUD BREACH EXECUTIVE SUMMARY' }),
    t('cb-2', 'component', 20, 90, 290, 250, { type: 'chart', source: 'anomaly', title: 'IAM Privilege Escalation' }),
    t('cb-3', 'component', 330, 90, 290, 250, { type: 'chart', source: 'timeline', title: 'AWS API Access Log' }),
    t('cb-4', 'component', 20, 350, 600, 250, { type: 'network-flow', source: 'network', title: 'S3 Bucket Egress' })
  ]
}
