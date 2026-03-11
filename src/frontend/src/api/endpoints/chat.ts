import { apiClient } from '../client';
import { ChatRequest, ChatResponse } from '../types';

export const chatAPI = {
  /**
   * 发送聊天消息（非流式）
   */
  async chat(request: ChatRequest): Promise<ChatResponse> {
    return apiClient.post<ChatResponse>('/api/chat', {
      ...request,
      stream: false,
      ...(request.session_id ? { session_id: request.session_id } : {}),
    });
  },

  /**
   * 发送聊天消息（流式）
   * 使用 fetch + ReadableStream 处理 SSE，返回 AbortController 用于取消
   */
  chatStream(
    request: ChatRequest,
    onChunk: (delta: string) => void,
    onSources: (sources: unknown[]) => void,
    onEvidence: (evidence: unknown[]) => void,
    onMeta: (meta: { quality_score?: number; retrieval_trace_id?: string }) => void,
    onDone: () => void,
    onError: (error: string) => void,
    onNodes?: (nodeIds: string[]) => void,
  ): AbortController {
    const controller = new AbortController();
    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

    fetch(`${baseURL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...request, stream: true, ...(request.session_id ? { session_id: request.session_id } : {}) }),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) {
          try {
            const body = await res.json();
            const detail = body?.detail;
            const msg = typeof detail === 'string' ? detail
              : Array.isArray(detail) ? detail.map((d: any) => d.msg ?? JSON.stringify(d)).join('; ')
              : JSON.stringify(detail);
            onError(`HTTP ${res.status}: ${msg}`);
          } catch {
            onError(`HTTP ${res.status}`);
          }
          return;
        }
        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        const handleLine = (line: string) => {
          if (!line.startsWith('data: ')) return;
          const raw = line.slice(6).trim();
          if (!raw) return;
          try {
            const msg = JSON.parse(raw) as {
              type: string;
              delta?: string;
              sources?: unknown[];
              evidence?: unknown[];
              error?: string;
              node_ids?: string[];
              quality_score?: number;
              retrieval_trace_id?: string;
            };
            if (msg.type === 'content' && msg.delta) onChunk(msg.delta);
            else if (msg.type === 'nodes' && msg.node_ids && onNodes) onNodes(msg.node_ids);
            else if (msg.type === 'sources' && msg.sources) onSources(msg.sources);
            else if (msg.type === 'evidence' && msg.evidence) onEvidence(msg.evidence);
            else if (msg.type === 'meta') onMeta({
              quality_score: msg.quality_score,
              retrieval_trace_id: msg.retrieval_trace_id,
            });
            else if (msg.type === 'done') onDone();
            else if (msg.type === 'error') onError(msg.error ?? '未知错误');
          } catch {
            // 忽略解析失败的行
          }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            handleLine(line);
          }
        }

        if (buffer.trim()) {
          handleLine(buffer.trim());
        }
      })
      .catch((err: Error) => {
        if (err.name !== 'AbortError') onError(err.message);
      });

    return controller;
  },
};
