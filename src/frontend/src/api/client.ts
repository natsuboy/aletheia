import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

interface EnhancedAxiosRequestConfig extends AxiosRequestConfig {
  dedupe?: boolean;
  dedupeKey?: string;
}

export class APIClient {
  private client: AxiosInstance;
  private inFlightGetRequests = new Map<string, Promise<unknown>>();

  constructor(baseURL: string = import.meta.env.VITE_API_BASE_URL) {
    this.client = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // 请求拦截器
    this.client.interceptors.request.use(
      (config) => {
        // 可以在这里添加认证 token
        return config;
      },
      (error) => Promise.reject(error)
    );

    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => response.data,
      (error) => {
        const message = error.response?.data?.detail || error.message || '请求失败';
        console.error('API Error:', message);
        return Promise.reject(new Error(message));
      }
    );
  }

  private buildGetDedupeKey(url: string, config?: EnhancedAxiosRequestConfig): string {
    if (config?.dedupeKey) return config.dedupeKey;
    const params = config?.params ? JSON.stringify(config.params) : '';
    return `GET:${url}?${params}`;
  }

  async get<T>(url: string, config?: EnhancedAxiosRequestConfig): Promise<T> {
    const dedupeEnabled = config?.dedupe !== false;
    if (!dedupeEnabled) {
      return this.client.get(url, config);
    }

    const dedupeKey = this.buildGetDedupeKey(url, config);
    const existing = this.inFlightGetRequests.get(dedupeKey);
    if (existing) {
      return existing as Promise<T>;
    }

    const requestPromise = this.client.get(url, config) as Promise<T>;
    this.inFlightGetRequests.set(dedupeKey, requestPromise as Promise<unknown>);
    requestPromise.finally(() => {
      this.inFlightGetRequests.delete(dedupeKey);
    });
    return requestPromise;
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.client.post(url, data, config);
  }

  async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.client.put(url, data, config);
  }

  async postForm<T>(url: string, formData: FormData, config?: AxiosRequestConfig): Promise<T> {
    return this.client.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      ...config,
    });
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.client.delete(url, config);
  }
}

export const apiClient = new APIClient();
