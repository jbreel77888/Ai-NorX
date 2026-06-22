/**
 * API client for backend communication
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async request<T>(
    endpoint: string,
    options: RequestInit = {},
    token?: string
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  async get<T>(endpoint: string, token?: string): Promise<T> {
    return this.request<T>(endpoint, { method: "GET" }, token);
  }

  async post<T>(endpoint: string, data?: any, token?: string): Promise<T> {
    return this.request<T>(
      endpoint,
      { method: "POST", body: data ? JSON.stringify(data) : undefined },
      token
    );
  }

  async patch<T>(endpoint: string, data: any, token?: string): Promise<T> {
    return this.request<T>(
      endpoint,
      { method: "PATCH", body: JSON.stringify(data) },
      token
    );
  }

  async delete<T>(endpoint: string, token?: string): Promise<T> {
    return this.request<T>(endpoint, { method: "DELETE" }, token);
  }
}

export const apiClient = new ApiClient();

// ━━━ Types ━━━

export interface Agent {
  id: string;
  name: string;
  description?: string;
  system_prompt: string;
  llm_provider: string;
  llm_model: string;
  temperature: number;
  max_tokens: number;
  tools: string[];
  conversation_starters: string[];
  visibility: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  title?: string;
  agent_id?: string;
  message_count: number;
  total_tokens: number;
  total_cost: number;
  is_pinned: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: string;
  content: string;
  reasoning?: string;
  tool_calls: any[];
  model_used?: string;
  provider?: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  created_at: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  free: boolean;
}

// ━━━ Agents API ━━━

export const agentsApi = {
  list: (token: string) => apiClient.get<Agent[]>("/api/v1/agents", token),

  get: (id: string, token: string) =>
    apiClient.get<Agent>(`/api/v1/agents/${id}`, token),

  create: (data: Partial<Agent>, token: string) =>
    apiClient.post<Agent>("/api/v1/agents", data, token),

  update: (id: string, data: Partial<Agent>, token: string) =>
    apiClient.patch<Agent>(`/api/v1/agents/${id}`, data, token),

  delete: (id: string, token: string) =>
    apiClient.delete(`/api/v1/agents/${id}`, token),

  models: (token: string) =>
    apiClient.get<Record<string, ModelInfo[]>>(
      "/api/v1/agents/models/list",
      token
    ),
};

// ━━━ Conversations API ━━━

export const conversationsApi = {
  list: (token: string) => apiClient.get<Conversation[]>("/api/v1/conversations", token),

  get: (id: string, token: string) =>
    apiClient.get<Conversation>(`/api/v1/conversations/${id}`, token),

  create: (data: { title?: string; agent_id?: string }, token: string) =>
    apiClient.post<Conversation>("/api/v1/conversations", data, token),

  delete: (id: string, token: string) =>
    apiClient.delete(`/api/v1/conversations/${id}`, token),

  messages: (id: string, token: string) =>
    apiClient.get<Message[]>(`/api/v1/conversations/${id}/messages`, token),
};
