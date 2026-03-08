/** Shared types for the JARVIS assistant UI. */

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  metadata?: ChatMetadata;
  structured_data?: Record<string, unknown> | null;
}

export interface ChatMetadata {
  request_type?: string;
  decision?: string;
  decision_explanation?: string;
  reasoning_steps?: string[];
  goal?: string;
  tools_used?: string[];
  patterns_detected?: string[];
  total_time_ms?: number;
}

export interface ChatApiResponse {
  status: string;
  request_id: string;
  response: {
    text: string;
    format: string;
    structured_data?: Record<string, unknown> | null;
  };
  metadata: ChatMetadata;
}

export interface HealthStatus {
  status: string;
  version: string;
  uptime_seconds: number;
  services: Record<string, boolean>;
  voice_available: boolean;
}
