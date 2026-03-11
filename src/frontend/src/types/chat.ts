export interface MessageStep {
  id: string;
  type: 'reasoning' | 'tool_call' | 'content';
  content?: string;
  toolCall?: ToolCallInfo;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  steps?: MessageStep[];
  timestamp: number;
  sources?: ChatSource[];
  evidence?: ChatEvidence[];
  qualityScore?: number;
  retrievalTraceId?: string;
}

export interface ChatSource {
  text: string;
  source: string;
  score: number;
  metadata?: Record<string, unknown>;
}

export interface ChatEvidence {
  id: string;
  content: string;
  sourceType: string;
  score: number;
  filePath?: string;
  symbol?: string;
  metadata?: Record<string, unknown>;
}

export interface ToolCallInfo {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status: 'pending' | 'running' | 'completed' | 'error';
}
