import { apiClient } from '../client';
import type { ResearchSession } from '../../types/research';

export const researchAPI = {
  async start(query: string, projectId: string): Promise<ResearchSession> {
    return apiClient.post<ResearchSession>('/api/research/start', {
      query,
      project_id: projectId,
    });
  },

  async continue(sessionId: string, projectId: string): Promise<ResearchSession> {
    return apiClient.post<ResearchSession>(`/api/research/${sessionId}/continue`, {
      project_id: projectId,
    });
  },

  async getSession(sessionId: string, projectId: string): Promise<ResearchSession> {
    return apiClient.get<ResearchSession>(`/api/research/${sessionId}`, {
      params: { project_id: projectId },
    });
  },

  async conclude(sessionId: string, projectId: string): Promise<ResearchSession> {
    return apiClient.post<ResearchSession>(`/api/research/${sessionId}/conclude`, {
      project_id: projectId,
    });
  },
};
