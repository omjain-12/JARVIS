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

export type LiveVoiceState =
  | "idle"
  | "listening"
  | "transcribing"
  | "thinking"
  | "speaking";


// ── Data Types ──

export interface TaskItem {
  id: string;
  title: string;
  description: string;
  priority: number;
  status: string;
  due_date: string;
}

export interface ReminderItem {
  id: string;
  title: string;
  message: string;
  remind_at: string;
  is_sent: boolean;
}

export interface ContactItem {
  id: string;
  name: string;
  email: string;
  phone: string;
  relationship?: string;
  notes?: string;
  created_at?: string;
}

export interface HabitItem {
  id: string;
  name: string;
  description: string;
  frequency: string;
  streak: number;
  total_completions: number;
  last_completed: string;
}

export interface KnowledgeEntry {
  content: string;
  score?: number;
  topic?: string;
  source_filename?: string;
  timestamp?: string;
}

export interface LearnedFact {
  summary: string;
  key: string;
  value: string;
  topic: string;
  confidence: number;
  source: string;
  captured_at: string;
}

export interface MemoriesResponse {
  learned_facts: LearnedFact[];
  behavior_patterns: KnowledgeEntry[];
  knowledge_entries: KnowledgeEntry[];
  conversation_history: { role: string; content: string; timestamp: string }[];
}
