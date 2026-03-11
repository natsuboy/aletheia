import { apiClient } from '../client';
import type {
  EntrypointReverseLookupResponse,
  GinEndpointSearchResponse,
  ReferenceSubgraphResponse,
} from '../types';

export const navAPI = {
  async searchGinEndpoints(projectId: string, query: string, limit = 30): Promise<GinEndpointSearchResponse> {
    return apiClient.get<GinEndpointSearchResponse>(`/api/nav/${projectId}/gin/endpoints`, {
      params: { q: query, limit },
    });
  },

  async getReferences(
    projectId: string,
    symbol: string,
    direction: 'in' | 'out' | 'both' = 'both',
    depth = 2,
    limit = 300,
  ): Promise<ReferenceSubgraphResponse> {
    return apiClient.get<ReferenceSubgraphResponse>(`/api/nav/${projectId}/references`, {
      params: { symbol, direction, depth, limit },
    });
  },

  async reverseLookupEntrypoint(projectId: string, nodeId: string, limit = 20): Promise<EntrypointReverseLookupResponse> {
    return apiClient.get<EntrypointReverseLookupResponse>(`/api/nav/${projectId}/entrypoint/${nodeId}`, {
      params: { limit },
    });
  },
};
