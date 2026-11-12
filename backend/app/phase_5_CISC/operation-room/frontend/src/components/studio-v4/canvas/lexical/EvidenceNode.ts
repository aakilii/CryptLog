import { TextNode, NodeKey, EditorConfig, SerializedTextNode } from 'lexical';

export class EvidenceNode extends TextNode {
  static getType(): string {
    return 'evidence-node';
  }

  static clone(node: EvidenceNode): EvidenceNode {
    return new EvidenceNode(node.__text, node.__key);
  }

  constructor(text: string, key?: NodeKey) {
    super(text, key);
  }

  createDOM(config: EditorConfig): HTMLElement {
    const dom = super.createDOM(config);
    dom.className = 'inline-flex items-center mx-1 px-1.5 py-0.5 rounded bg-sky-100 dark:bg-sky-900/40 text-sky-800 dark:text-sky-300 border border-sky-200 dark:border-sky-800 text-xs font-mono font-bold select-none overflow-hidden isolate';
    return dom;
  }

  updateDOM(): boolean {
    return false;
  }
  
  static importJSON(serializedNode: SerializedTextNode): EvidenceNode {
    const node = $createEvidenceNode(serializedNode.text);
    node.setFormat(serializedNode.format);
    node.setDetail(serializedNode.detail);
    node.setMode(serializedNode.mode);
    node.setStyle(serializedNode.style);
    return node;
  }

  exportJSON(): SerializedTextNode {
    return {
      ...super.exportJSON(),
      type: 'evidence-node',
      version: 1,
    };
  }

  isSegmented(): boolean {
    return true; 
  }
}

export function $createEvidenceNode(text: string): EvidenceNode {
  const node = new EvidenceNode(text);
  // Setting mode to 'token' forces the engine to delete the entire text node at once
  node.setMode('token');
  return node;
}

export function $isEvidenceNode(node: any): node is EvidenceNode {
  return node instanceof EvidenceNode;
}
