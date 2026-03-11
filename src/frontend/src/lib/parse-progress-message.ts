export interface ParsedProgress {
  nodesInserted?: number;
  nodesTotal?: number;
  edgesInserted?: number;
  edgesTotal?: number;
  documentsCount?: number;
}

const NODE_RE = /节点\s*(\d+)\s*[/／]\s*(\d+)/;
const EDGE_RE = /边\s*(\d+)\s*[/／]\s*(\d+)/;
const DOC_RE = /(\d+)\s*个文档/;
const MAPPING_RE = /(\d+)\s*节点[,，]\s*(\d+)\s*边/;
const EMBED_RE = /向量嵌入\s*(\d+)\s*[/／]\s*(\d+)/;

export function parseProgressMessage(message: string): ParsedProgress {
  const result: ParsedProgress = {};

  const nodeMatch = message.match(NODE_RE);
  if (nodeMatch) {
    result.nodesInserted = parseInt(nodeMatch[1], 10);
    result.nodesTotal = parseInt(nodeMatch[2], 10);
  }

  const edgeMatch = message.match(EDGE_RE);
  if (edgeMatch) {
    result.edgesInserted = parseInt(edgeMatch[1], 10);
    result.edgesTotal = parseInt(edgeMatch[2], 10);
  }

  const docMatch = message.match(DOC_RE);
  if (docMatch) {
    result.documentsCount = parseInt(docMatch[1], 10);
  }

  // "映射完成: 1247 节点, 5032 边" — 提取总数
  const mappingMatch = message.match(MAPPING_RE);
  if (mappingMatch) {
    result.nodesTotal = parseInt(mappingMatch[1], 10);
    result.edgesTotal = parseInt(mappingMatch[2], 10);
  }

  // "正在生成向量嵌入 100/500..." — 复用 nodes 字段表示嵌入进度
  const embedMatch = message.match(EMBED_RE);
  if (embedMatch && !nodeMatch) {
    result.nodesInserted = parseInt(embedMatch[1], 10);
    result.nodesTotal = parseInt(embedMatch[2], 10);
  }

  return result;
}
