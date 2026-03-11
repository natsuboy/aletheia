import { apiClient } from '../client';
import { Project, IngestRequest, JobStatus } from '../types';

export const projectAPI = {
  /**
   * 获取所有项目列表
   */
  async getProjects(): Promise<Project[]> {
    const res = await apiClient.get<{ projects: Project[]; total: number }>('/api/projects');
    return res.projects;
  },

  /**
   * 获取单个项目详情
   */
  async getProject(projectId: string): Promise<Project> {
    return apiClient.get<Project>(`/api/projects/${projectId}`);
  },

  /**
   * 提交代码仓库索引任务
   */
  async submitIngest(data: IngestRequest): Promise<{ job_id: string }> {
    return apiClient.post<{ job_id: string }>('/api/ingest', data);
  },

  /**
   * 查询索引任务状态
   */
  async getJobStatus(jobId: string): Promise<JobStatus> {
    return apiClient.get<JobStatus>(`/api/jobs/${jobId}`);
  },

  /**
   * 按项目恢复当前活跃任务（页面刷新恢复用）
   */
  async getActiveJob(projectId: string): Promise<{ active: boolean; job: JobStatus | null }> {
    return apiClient.get<{ active: boolean; job: JobStatus | null }>(`/api/projects/${projectId}/jobs/active`);
  },

  /**
   * 上传 SCIP 文件
   */
  async uploadScip(
    file: File,
    projectName: string,
    onUploadProgress?: (percent: number) => void,
  ): Promise<{ job_id: string }> {
    const form = new FormData();
    form.append('file', file);
    form.append('project_name', projectName);
    return apiClient.postForm<{ job_id: string }>('/api/ingest/scip-upload', form, {
      onUploadProgress: onUploadProgress
        ? (e) => {
            const pct = e.total ? Math.round((e.loaded * 100) / e.total) : 0;
            onUploadProgress(pct);
          }
        : undefined,
    });
  },

  /**
   * 取消进行中的任务
   */
  async cancelJob(jobId: string): Promise<{ job_id: string; status: string }> {
    return apiClient.post<{ job_id: string; status: string }>(`/api/jobs/${jobId}/cancel`, {});
  },

  /**
   * 删除项目（异步，返回 job_id 供轮询）
   */
  async deleteProject(projectId: string): Promise<{ job_id: string }> {
    return apiClient.delete<{ job_id: string }>(`/api/projects/${projectId}`);
  },
};
