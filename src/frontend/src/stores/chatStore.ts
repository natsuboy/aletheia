import { create } from 'zustand';
import { chatAPI } from '../api';
import { useGraphStore } from './graphStore';
import type { ChatMessage, ChatSource, ChatEvidence, MessageStep } from '../types/chat';

interface ChatState {
  messages: ChatMessage[];
  currentAnswer: string;
  currentSteps: MessageStep[];
  isStreaming: boolean;
  loading: boolean;
  error: string | null;
  _abortController: AbortController | null;
  _currentProjectId: string | null;

  // 多轮对话
  sessionId: string | null;

  // Research 模式
  isResearchMode: boolean;
  researchSessionId: string | null;
  researchIteration: number;
  researchMaxIterations: number;
  researchStatus: 'idle' | 'active' | 'concluded';

  sendMessage: (query: string, projectId: string) => Promise<void>;
  loadHistory: (projectId: string) => void;
  clearChat: () => void;
  clearHistory: () => void;
  stopStreaming: () => void;
  clearError: () => void;
  newSession: () => void;
  setResearchMode: (enabled: boolean) => void;
  setResearchState: (state: Partial<Pick<ChatState, 'researchSessionId' | 'researchIteration' | 'researchStatus'>>) => void;
}

const MAX_PERSISTED = 50;

function saveToStorage(projectId: string, messages: ChatMessage[]) {
  try {
    const key = `aletheia-chat-${projectId}`;
    localStorage.setItem(key, JSON.stringify(messages.slice(-MAX_PERSISTED)));
  } catch { /* full */ }
}

function loadFromStorage(projectId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(`aletheia-chat-${projectId}`);
    if (!raw) return [];
    return JSON.parse(raw) as ChatMessage[];
  } catch { return []; }
}

function getOrCreateSessionId(projectId: string): string {
  const key = `aletheia-session-${projectId}`;
  let sid = localStorage.getItem(key);
  if (!sid) {
    sid = crypto.randomUUID();
    localStorage.setItem(key, sid);
  }
  return sid;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  currentAnswer: '',
  currentSteps: [],
  isStreaming: false,
  loading: false,
  error: null,
  _abortController: null,
  _currentProjectId: null,
  sessionId: null,
  isResearchMode: false,
  researchSessionId: null,
  researchIteration: 0,
  researchMaxIterations: 5,
  researchStatus: 'idle',

  sendMessage: async (query, projectId) => {
    const { sessionId } = get();
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
      timestamp: Date.now(),
    };

    set({
      messages: [...get().messages, userMsg],
      isStreaming: true,
      loading: true,
      currentAnswer: '',
      currentSteps: [],
      error: null,
    });

    let pendingSources: ChatSource[] | undefined;
    let pendingEvidence: ChatEvidence[] | undefined;
    let pendingQualityScore: number | undefined;
    let pendingRetrievalTraceId: string | undefined;

    const controller = chatAPI.chatStream(
      { query, project_id: projectId, stream: true, session_id: sessionId ?? undefined },
      (delta) => {
        set((s) => ({ currentAnswer: s.currentAnswer + delta }));
      },
      (sources) => {
        pendingSources = Array.isArray(sources)
          ? sources.map((s) => {
              const src = s as Record<string, unknown>;
              return {
                text: String(src.text ?? src.content ?? ''),
                source: String(src.source ?? src.file_path ?? ''),
                score: Number(src.score ?? 0.9),
                metadata: (src.metadata as Record<string, unknown>) ?? {},
              };
            })
          : undefined;
      },
      (evidence) => {
        pendingEvidence = Array.isArray(evidence)
          ? evidence.map((item, idx) => {
              const ev = item as Record<string, unknown>;
              return {
                id: String(ev.id ?? `ev-${idx}`),
                content: String(ev.content ?? ev.text ?? ''),
                sourceType: String(ev.source_type ?? ev.source ?? 'unknown'),
                score: Number(ev.score ?? 0),
                filePath: ev.file_path ? String(ev.file_path) : undefined,
                symbol: ev.symbol ? String(ev.symbol) : undefined,
                metadata: (ev.metadata as Record<string, unknown>) ?? {},
              };
            })
          : undefined;
      },
      (meta) => {
        pendingQualityScore = typeof meta.quality_score === 'number' ? meta.quality_score : undefined;
        pendingRetrievalTraceId = typeof meta.retrieval_trace_id === 'string' ? meta.retrieval_trace_id : undefined;
      },
      () => {
        const state = get();
        const contentStep: MessageStep = {
          id: crypto.randomUUID(),
          type: 'content',
          content: state.currentAnswer,
        };
        const assistantMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: state.currentAnswer,
          steps: [contentStep],
          timestamp: Date.now(),
          sources: pendingSources,
          evidence: pendingEvidence,
          qualityScore: pendingQualityScore,
          retrievalTraceId: pendingRetrievalTraceId,
        };
        const newMessages = [...state.messages, assistantMsg];
        set({
          messages: newMessages,
          currentAnswer: '',
          currentSteps: [],
          isStreaming: false,
          loading: false,
          _abortController: null,
        });
        saveToStorage(projectId, newMessages);
      },
      (error) => {
        set({ error, isStreaming: false, loading: false, currentAnswer: '', _abortController: null });
      },
      (nodeIds) => {
        useGraphStore.getState().setAICitationHighlights(new Set(nodeIds));
      },
    );
    set({ _abortController: controller });
  },

  stopStreaming: () => {
    const { _abortController, currentAnswer } = get();
    _abortController?.abort();
    if (currentAnswer) {
      const msg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: currentAnswer,
        steps: [{ id: crypto.randomUUID(), type: 'content', content: currentAnswer }],
        timestamp: Date.now(),
      };
      set({
        messages: [...get().messages, msg],
        currentAnswer: '',
        currentSteps: [],
        isStreaming: false,
        loading: false,
        _abortController: null,
      });
    } else {
      set({ isStreaming: false, loading: false, _abortController: null });
    }
  },

  loadHistory: (projectId) => {
    const messages = loadFromStorage(projectId);
    const sessionId = getOrCreateSessionId(projectId);
    set({ messages, _currentProjectId: projectId, sessionId, currentAnswer: '', isStreaming: false, loading: false, error: null });
  },

  clearChat: () => {
    const { _abortController, _currentProjectId } = get();
    _abortController?.abort();
    set({ messages: [], currentAnswer: '', currentSteps: [], isStreaming: false, loading: false, _abortController: null });
    if (_currentProjectId) saveToStorage(_currentProjectId, []);
  },

  newSession: () => {
    const { _currentProjectId } = get();
    if (_currentProjectId) {
      const newSid = crypto.randomUUID();
      localStorage.setItem(`aletheia-session-${_currentProjectId}`, newSid);
      set({
        sessionId: newSid,
        messages: [],
        currentAnswer: '',
        currentSteps: [],
        isStreaming: false,
        loading: false,
        researchSessionId: null,
        researchIteration: 0,
        researchStatus: 'idle',
      });
      saveToStorage(_currentProjectId, []);
    }
  },

  clearHistory: () => {
    const { _currentProjectId } = get();
    if (_currentProjectId) localStorage.removeItem(`aletheia-chat-${_currentProjectId}`);
    set({ messages: [] });
  },

  clearError: () => set({ error: null }),

  setResearchMode: (enabled) => set({
    isResearchMode: enabled,
    ...(enabled ? {} : { researchSessionId: null, researchIteration: 0, researchStatus: 'idle' }),
  }),

  setResearchState: (partial) => set(partial),
}));
