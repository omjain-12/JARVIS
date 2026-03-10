/**
 * API service — fetch wrappers for the JARVIS backend.
 *
 * All calls go through the Next.js rewrite (/api/* → localhost:8001/*).
 */

import type {
  ChatApiResponse,
  HealthStatus,
  TaskItem,
  ReminderItem,
  ContactItem,
  HabitItem,
  KnowledgeEntry,
  MemoriesResponse,
} from "@/types";

const BASE = "/api";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

/** Send a chat message and get the agent response. */
export async function sendMessage(
  userId: string,
  message: string,
  sessionId = "",
): Promise<ChatApiResponse> {
  return post<ChatApiResponse>("/chat", {
    user_id: userId,
    message,
    session_id: sessionId,
  });
}

/** Confirm or reject a pending action. */
export async function confirmAction(
  actionId: string,
  confirmed: boolean,
  toolName = "",
  toolParams: Record<string, unknown> = {},
): Promise<{ status: string; message: string; result?: Record<string, unknown> }> {
  return post("/confirm", {
    action_id: actionId,
    confirmed,
    tool_name: toolName,
    tool_params: toolParams,
  });
}

/** Upload audio and receive transcribed text. */
export async function voiceToText(audioBlob: Blob): Promise<string> {
  const form = new FormData();
  form.append("file", audioBlob, "recording.wav");

  const res = await fetch(`${BASE}/voice-to-text`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    throw new Error("Voice recognition failed");
  }

  const data = await res.json();
  return data.text as string;
}

/** Convert text to speech — returns audio blob. */
export async function textToVoice(
  text: string,
  voiceName = "en-US-GuyNeural",
): Promise<Blob> {
  const res = await fetch(`${BASE}/text-to-voice`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice_name: voiceName }),
  });

  if (!res.ok) {
    throw new Error("Text-to-speech failed");
  }

  return res.blob();
}

/** Health check. */
export async function getHealth(): Promise<HealthStatus> {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json() as Promise<HealthStatus>;
}

// ── Data API helpers ──

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Request failed (${res.status})`);
  }
}

// ── Tasks ──

export async function getTasks(
  userId = "demo_user",
  status = "",
): Promise<TaskItem[]> {
  const params = new URLSearchParams({ user_id: userId });
  if (status) params.append("status", status);
  const data = await get<{ tasks: TaskItem[] }>(`/data/tasks?${params}`);
  return data.tasks;
}

export async function createTask(
  title: string,
  description = "",
  priority = 0,
  dueDate = "",
  userId = "demo_user",
): Promise<TaskItem> {
  const data = await post<{ task: TaskItem }>(`/data/tasks?user_id=${userId}`, {
    title,
    description,
    priority,
    due_date: dueDate,
  });
  return data.task;
}

export async function updateTaskStatus(
  taskId: string,
  status: string,
): Promise<void> {
  const res = await fetch(`${BASE}/data/tasks/${taskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("Failed to update task");
}

// ── Reminders ──

export async function getReminders(
  userId = "demo_user",
): Promise<ReminderItem[]> {
  const data = await get<{ reminders: ReminderItem[] }>(
    `/data/reminders?user_id=${userId}`,
  );
  return data.reminders;
}

export async function createReminder(
  title: string,
  message: string,
  remindAt: string,
  userId = "demo_user",
): Promise<ReminderItem> {
  const data = await post<{ reminder: ReminderItem }>(
    `/data/reminders?user_id=${userId}`,
    { title, message, remind_at: remindAt },
  );
  return data.reminder;
}

// ── Contacts ──

export async function getContacts(
  userId = "demo_user",
): Promise<ContactItem[]> {
  const data = await get<{ contacts: ContactItem[] }>(
    `/data/contacts?user_id=${userId}`,
  );
  return data.contacts;
}

export async function createContact(
  contact: { name: string; email?: string; phone?: string; relationship?: string; notes?: string },
  userId = "demo_user",
): Promise<ContactItem> {
  const data = await post<{ contact: ContactItem }>(
    `/data/contacts?user_id=${userId}`,
    contact,
  );
  return data.contact;
}

export async function updateContact(
  contactId: string,
  contact: Partial<ContactItem>,
): Promise<ContactItem> {
  const res = await fetch(`${BASE}/data/contacts/${contactId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(contact),
  });
  if (!res.ok) throw new Error("Failed to update contact");
  const data = await res.json();
  return data.contact as ContactItem;
}

export async function deleteContact(contactId: string): Promise<void> {
  await del(`/data/contacts/${contactId}`);
}

// ── Habits ──

export async function getHabits(
  userId = "demo_user",
): Promise<HabitItem[]> {
  const data = await get<{ habits: HabitItem[] }>(
    `/data/habits?user_id=${userId}`,
  );
  return data.habits;
}

// ── Preferences ──

export async function getPreferences(
  userId = "demo_user",
): Promise<Record<string, unknown>[]> {
  const data = await get<{ preferences: Record<string, unknown>[] }>(
    `/data/preferences?user_id=${userId}`,
  );
  return data.preferences;
}

// ── Knowledge ──

export async function addKnowledge(
  content: string,
  topic = "general",
  userId = "demo_user",
): Promise<void> {
  await post(`/data/knowledge?user_id=${userId}`, { content, topic });
}

export async function searchKnowledge(
  query = "",
  userId = "demo_user",
): Promise<KnowledgeEntry[]> {
  const params = new URLSearchParams({ user_id: userId });
  if (query) params.append("query", query);
  const data = await get<{ knowledge: KnowledgeEntry[] }>(
    `/data/knowledge?${params}`,
  );
  return data.knowledge;
}

// ── Memory Viewer ──

export async function getMemories(
  userId = "demo_user",
): Promise<MemoriesResponse> {
  return get<MemoriesResponse>(`/data/memories?user_id=${userId}`);
}
