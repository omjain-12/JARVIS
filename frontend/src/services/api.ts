/**
 * API service — fetch wrappers for the JARVIS backend.
 *
 * All calls go through the Next.js rewrite (/api/* → localhost:8001/*).
 */

import type { ChatApiResponse, HealthStatus } from "@/types";

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
): Promise<{ status: string; message: string }> {
  return post("/confirm", { action_id: actionId, confirmed });
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
  voiceName = "en-US-JennyNeural",
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
