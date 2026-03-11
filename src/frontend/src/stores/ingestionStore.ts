import { create } from 'zustand';
import { parseProgressMessage } from '@/lib/parse-progress-message';
import { projectAPI } from '@/api';

export type StageStatus = 'pending' | 'active' | 'completed' | 'failed';

export interface StageInfo {
  name: string;
  label: string;
  status: StageStatus;
  startedAt: number | null;
  completedAt: number | null;
  subProgress: number | null;
  subMessage: string | null;
}

export interface ParsedMetrics {
  nodesInserted: number | null;
  nodesTotal: number | null;
  edgesInserted: number | null;
  edgesTotal: number | null;
  documentsCount: number | null;
}

export interface ActivityLogEntry {
  ts: number;
  message: string;
}

type FlowType = 'scip' | 'repo';
type OverallStatus = 'idle' | 'uploading' | 'processing' | 'completed' | 'failed';

const SCIP_STAGES = ['uploading', 'parsing', 'mapping', 'inserting', 'vectorizing'];
const REPO_STAGES = ['cloning', 'indexing', 'parsing', 'mapping', 'inserting', 'vectorizing'];

const STAGE_LABELS: Record<string, string> = {
  uploading: 'Uploading',
  cloning: 'Cloning',
  indexing: 'Indexing',
  parsing: 'Parsing',
  mapping: 'Mapping',
  inserting: 'Inserting',
  vectorizing: 'Vectorizing',
};

function buildStages(flow: FlowType): StageInfo[] {
  const names = flow === 'scip' ? SCIP_STAGES : REPO_STAGES;
  return names.map((name) => ({
    name,
    label: STAGE_LABELS[name] || name,
    status: 'pending' as StageStatus,
    startedAt: null,
    completedAt: null,
    subProgress: null,
    subMessage: null,
  }));
}

const MAX_LOG_ENTRIES = 50;

interface IngestionState {
  jobId: string | null;
  projectName: string | null;
  flowType: FlowType;
  status: OverallStatus;
  overallProgress: number;
  currentStage: string | null;
  writePhase: string | null;
  itemsTotal: number | null;
  itemsDone: number | null;
  stages: StageInfo[];
  metrics: ParsedMetrics;
  activityLog: ActivityLogEntry[];
  startedAt: number | null;
  error: string | null;
  traceId: string | null;
  retryCount: number;
  failureClass: string | null;
  _ws: WebSocket | null;
  _pollTimer: ReturnType<typeof setTimeout> | null;
  _reconnectAttempts: number;
  _pollRetries: number;

  // Actions
  startScipUpload: (file: File, projectName: string, onUploadProgress?: (pct: number) => void) => Promise<string>;
  startRepoIngest: (repoUrl: string, language: string, projectName?: string) => Promise<string>;
  connectWebSocket: (projectName: string) => void;
  restoreProjectProgress: (projectName: string) => Promise<void>;
  pollJobStatus: (jobId: string) => void;
  processMessage: (data: Record<string, unknown>) => void;
  cancelJob: () => Promise<void>;
  disconnect: () => void;
  reset: () => void;
}

const INITIAL_METRICS: ParsedMetrics = {
  nodesInserted: null,
  nodesTotal: null,
  edgesInserted: null,
  edgesTotal: null,
  documentsCount: null,
};

export const useIngestionStore = create<IngestionState>((set, get) => ({
  jobId: null,
  projectName: null,
  flowType: 'scip',
  status: 'idle',
  overallProgress: 0,
  currentStage: null,
  writePhase: null,
  itemsTotal: null,
  itemsDone: null,
  stages: [],
  metrics: { ...INITIAL_METRICS },
  activityLog: [],
  startedAt: null,
  error: null,
  traceId: null,
  retryCount: 0,
  failureClass: null,
  _ws: null,
  _pollTimer: null,
  _reconnectAttempts: 0,
  _pollRetries: 0,

  startScipUpload: async (file, projectName, onUploadProgress) => {
    const stages = buildStages('scip');
    stages[0].status = 'active';
    stages[0].startedAt = Date.now();

    set({
      flowType: 'scip',
      projectName,
      status: 'uploading',
      stages,
      currentStage: 'uploading',
      writePhase: 'prepare',
      itemsTotal: null,
      itemsDone: null,
      overallProgress: 0,
      metrics: { ...INITIAL_METRICS },
      activityLog: [{ ts: Date.now(), message: '开始上传 SCIP 文件...' }],
      startedAt: Date.now(),
      error: null,
      traceId: null,
      retryCount: 0,
      failureClass: null,
    });

    const { job_id } = await projectAPI.uploadScip(file, projectName, (pct) => {
      const s = get().stages.map((st) =>
        st.name === 'uploading' ? { ...st, subProgress: pct, subMessage: `${pct}%` } : st,
      );
      set({ stages: s, overallProgress: Math.round(pct * 0.1) });
      onUploadProgress?.(pct);
    });

    // 标记 uploading 完成
    const now = Date.now();
    const updated = get().stages.map((st) =>
      st.name === 'uploading' ? { ...st, status: 'completed' as StageStatus, completedAt: now, subProgress: 100 } : st,
    );
    set({ jobId: job_id, stages: updated, status: 'processing', overallProgress: 10 });

    localStorage.setItem(`job:${job_id}`, job_id);
    get().connectWebSocket(projectName);

    return job_id;
  },

  startRepoIngest: async (repoUrl, language, projectName) => {
    const stages = buildStages('repo');
    set({
      flowType: 'repo',
      projectName: projectName || null,
      status: 'processing',
      stages,
      currentStage: null,
      writePhase: 'prepare',
      itemsTotal: null,
      itemsDone: null,
      overallProgress: 0,
      metrics: { ...INITIAL_METRICS },
      activityLog: [{ ts: Date.now(), message: '提交索引任务...' }],
      startedAt: Date.now(),
      error: null,
      traceId: null,
      retryCount: 0,
      failureClass: null,
    });

    const { job_id } = await projectAPI.submitIngest({
      repo_url: repoUrl,
      language,
      project_name: projectName,
    });
    const derivedName = projectName || repoUrl.replace(/\.git$/, '').split('/').pop() || 'project';

    set({ jobId: job_id, projectName: derivedName });
    localStorage.setItem(`job:${job_id}`, job_id);
    get().connectWebSocket(derivedName);

    return job_id;
  },

  connectWebSocket: (projectName) => {
    get().disconnect();
    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    const wsURL = baseURL.replace(/^http/, 'ws') + `/ws/${encodeURIComponent(projectName)}`;

    const connect = (attempt: number) => {
      const ws = new WebSocket(wsURL);

      ws.onopen = () => {
        set({ _ws: ws, _reconnectAttempts: 0 });
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          get().processMessage(data);
        } catch { /* ignore */ }
      };

      ws.onerror = () => {
        // 启用轮询备用
        const { jobId } = get();
        if (jobId) get().pollJobStatus(jobId);
      };

      ws.onclose = () => {
        set({ _ws: null });
        const { status, _reconnectAttempts } = get();
        if (status === 'processing' && _reconnectAttempts < 5) {
          const delay = Math.min(1000 * Math.pow(2, attempt), 16000);
          setTimeout(() => {
            set({ _reconnectAttempts: attempt + 1 });
            connect(attempt + 1);
          }, delay);
        }
      };

      set({ _ws: ws });
    };

    connect(0);
  },

  restoreProjectProgress: async (projectName) => {
    set({ projectName });
    try {
      const res = await projectAPI.getActiveJob(projectName);
      const snapshot = res.job;
      if (!snapshot) {
        get().connectWebSocket(projectName);
        return;
      }

      const stageName = (snapshot.stage || '') as string;
      const flowType: FlowType = stageName === 'uploading' ? 'scip' : 'repo';
      const stages = buildStages(flowType);
      const startedAt = snapshot.created_at ? Date.parse(snapshot.created_at) : Date.now();

      const mappedStatus: OverallStatus =
        snapshot.status === 'completed'
          ? 'completed'
          : snapshot.status === 'failed'
            ? 'failed'
            : stageName === 'uploading'
              ? 'uploading'
              : 'processing';

      set({
        flowType,
        jobId: snapshot.job_id,
        projectName,
        status: mappedStatus,
        stages,
        currentStage: stageName || null,
        writePhase: snapshot.write_phase ?? null,
        itemsTotal: snapshot.items_total ?? null,
        itemsDone: snapshot.items_done ?? null,
        overallProgress: Number(snapshot.progress ?? 0),
        startedAt,
        error: snapshot.error || null,
        traceId: snapshot.trace_id || null,
        retryCount: Number(snapshot.retry_count ?? 0),
        failureClass: snapshot.failure_class || null,
      });

      get().processMessage({
        stage: stageName,
        progress: snapshot.progress ?? 0,
        message: snapshot.message || '',
        status: snapshot.status,
        write_phase: snapshot.write_phase,
        items_total: snapshot.items_total,
        items_done: snapshot.items_done,
        error: snapshot.error,
        trace_id: snapshot.trace_id,
        retry_count: snapshot.retry_count,
        failure_class: snapshot.failure_class,
      });

      if (snapshot.status === 'pending' || snapshot.status === 'running') {
        get().connectWebSocket(projectName);
      } else if (snapshot.status !== 'failed') {
        // 已完成但可能仍有补充消息（例如最终写库日志），保持连接可见性一致
        get().connectWebSocket(projectName);
      }
    } catch {
      // 恢复失败时仍尝试直接连接 WS
      get().connectWebSocket(projectName);
    }
  },

  pollJobStatus: (jobId) => {
    // 清除已有的轮询
    const { _pollTimer } = get();
    if (_pollTimer) clearTimeout(_pollTimer);
    set({ _pollRetries: 0 });

    const MAX_POLL_RETRIES = 20;

    const poll = async () => {
      try {
        const status = await projectAPI.getJobStatus(jobId);
        set({ _pollRetries: 0 }); // 成功时重置计数
        get().processMessage({
          stage: status.stage || '',
          progress: status.progress ?? 0,
          message: status.message || '',
          status: status.status,
          write_phase: status.write_phase,
          items_total: status.items_total,
          items_done: status.items_done,
          error: status.error,
          trace_id: status.trace_id,
          retry_count: status.retry_count,
          failure_class: status.failure_class,
        });

        if (status.status === 'pending' || status.status === 'running') {
          const timer = setTimeout(poll, 2000);
          set({ _pollTimer: timer });
        }
      } catch {
        const retries = get()._pollRetries + 1;
        if (retries < MAX_POLL_RETRIES) {
          set({ _pollRetries: retries });
          const timer = setTimeout(poll, 3000);
          set({ _pollTimer: timer });
        } else {
          set({ status: 'failed', error: '无法连接服务器，轮询已停止', _pollTimer: null });
        }
      }
    };

    poll();
  },

  processMessage: (data) => {
    const stage = (data.stage as string) || '';
    const progress = (data.progress as number) ?? 0;
    const message = (data.message as string) || '';
    const msgStatus = (data.status as string) || '';
    const writePhase = (data.write_phase as string | undefined) ?? get().writePhase;
    const itemsTotal = data.items_total == null ? get().itemsTotal : Number(data.items_total);
    const itemsDone = data.items_done == null ? get().itemsDone : Number(data.items_done);
    const traceId = (data.trace_id as string) || null;
    const retryCount = Number(data.retry_count ?? get().retryCount ?? 0);
    const failureClass = (data.failure_class as string) || null;
    const now = Date.now();

    const currentState = get();
    const metrics = currentState.metrics;
    const shouldBootstrapStages = currentState.stages.length === 0;
    const inferredFlow: FlowType = stage === 'uploading' ? 'scip' : currentState.flowType || 'repo';
    const stages = shouldBootstrapStages ? buildStages(inferredFlow) : currentState.stages;

    // 解析消息中的结构化数据
    const parsed = parseProgressMessage(message);
    const newMetrics = { ...metrics };
    if (parsed.nodesInserted != null) newMetrics.nodesInserted = parsed.nodesInserted;
    if (parsed.nodesTotal != null) newMetrics.nodesTotal = parsed.nodesTotal;
    if (parsed.edgesInserted != null) newMetrics.edgesInserted = parsed.edgesInserted;
    if (parsed.edgesTotal != null) newMetrics.edgesTotal = parsed.edgesTotal;
    if (parsed.documentsCount != null) newMetrics.documentsCount = parsed.documentsCount;

    // 更新阶段状态
    const stageIdx = stages.findIndex((x) => x.name === stage);
    const newStages = stages.map((s, i) => {
      if (s.name === stage) {
        const stageStart = s.startedAt ?? now;
        const safeCompletedAt =
          s.completedAt != null && s.completedAt >= stageStart ? s.completedAt : null;
        return {
          ...s,
          status: msgStatus === 'failed' ? 'failed' as StageStatus : 'active' as StageStatus,
          startedAt: stageStart,
          // 乱序消息下，阶段被重新激活时清空异常 completedAt，避免出现负耗时。
          completedAt: safeCompletedAt,
          subProgress: progress,
          subMessage: message || s.subMessage,
        };
      } else if (stageIdx >= 0 && i < stageIdx && s.status !== 'completed') {
        const stageStart = s.startedAt ?? now;
        const stageEnd = s.completedAt != null && s.completedAt >= stageStart ? s.completedAt : now;
        return {
          ...s,
          status: 'completed' as StageStatus,
          startedAt: stageStart,
          completedAt: stageEnd,
        };
      }
      return s;
    });

    // 追加活动日志
    const log = get().activityLog;
    const newLog = message
      ? [{ ts: now, message }, ...log].slice(0, MAX_LOG_ENTRIES)
      : log;

    // 判断总体状态
    let newStatus: OverallStatus = 'processing';
    let newError: string | null = null;
    let finalStages = newStages;
    if (msgStatus === 'pending') {
      newStatus = stage === 'uploading' ? 'uploading' : 'processing';
    }
    if (msgStatus === 'completed' || stage === 'completed') {
      newStatus = 'completed';
      // 标记所有阶段为 completed（不可变方式）
      finalStages = newStages.map((s) =>
        s.status !== 'completed'
          ? (() => {
              const stageStart = s.startedAt ?? now;
              const stageEnd = s.completedAt != null && s.completedAt >= stageStart ? s.completedAt : now;
              return {
                ...s,
                status: 'completed' as StageStatus,
                startedAt: stageStart,
                completedAt: stageEnd,
              };
            })()
          : s,
      );
    } else if (msgStatus === 'failed') {
      newStatus = 'failed';
      newError = (data.error as string) || message || '任务失败';
    }

    set({
      flowType: inferredFlow,
      writePhase,
      itemsTotal,
      itemsDone,
      currentStage: stage === 'completed' ? null : stage,
      overallProgress: stage === 'completed' ? 100 : progress,
      stages: finalStages,
      metrics: newMetrics,
      activityLog: newLog,
      status: newStatus,
      error: newError,
      traceId,
      retryCount,
      failureClass,
    });
  },

  cancelJob: async () => {
    const { jobId } = get();
    if (!jobId) return;
    try {
      await projectAPI.cancelJob(jobId);
    } catch {
      // 即使请求失败也重置本地状态
    }
    get().disconnect();
    set({ status: 'failed', error: '任务已取消' });
  },

  disconnect: () => {
    const { _ws, _pollTimer } = get();
    if (_ws && _ws.readyState === WebSocket.OPEN) _ws.close();
    if (_pollTimer) clearTimeout(_pollTimer);
    set({ _ws: null, _pollTimer: null });
  },

  reset: () => {
    get().disconnect();
    set({
      jobId: null,
      projectName: null,
      status: 'idle',
      overallProgress: 0,
      currentStage: null,
      writePhase: null,
      itemsTotal: null,
      itemsDone: null,
      stages: [],
      metrics: { ...INITIAL_METRICS },
      activityLog: [],
      startedAt: null,
      error: null,
      traceId: null,
      retryCount: 0,
      failureClass: null,
      _reconnectAttempts: 0,
      _pollRetries: 0,
    });
  },
}));
