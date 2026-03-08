import React, { useCallback, useEffect, useRef, useState } from "react";
import Head from "next/head";
import Header from "@/components/Header";
import ChatWindow from "@/components/ChatWindow";
import ChatInput from "@/components/ChatInput";
import { sendMessage, getHealth, textToVoice } from "@/services/api";
import type { ChatMessage } from "@/types";

const USER_ID = "demo_user";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const [connected, setConnected] = useState(false);
  const sessionId = useRef(`session_${Date.now()}`);

  // ── Health check on mount ──
  useEffect(() => {
    getHealth()
      .then(() => setConnected(true))
      .catch(() => setConnected(false));
  }, []);

  // ── Play TTS audio ──
  const playAudio = useCallback(async (text: string) => {
    try {
      const blob = await textToVoice(text);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play();
      audio.onended = () => URL.revokeObjectURL(url);
    } catch {
      // TTS failed silently — text is already shown
    }
  }, []);

  // ── Send a message (text) ──
  const handleSend = useCallback(
    async (text: string) => {
      const userMsg: ChatMessage = {
        id: `user_${Date.now()}`,
        role: "user",
        content: text,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      try {
        const result = await sendMessage(USER_ID, text, sessionId.current);

        const assistantMsg: ChatMessage = {
          id: `asst_${Date.now()}`,
          role: "assistant",
          content: result.response.text || "I couldn't generate a response.",
          timestamp: Date.now(),
          metadata: result.metadata,
          structured_data: result.response.structured_data,
        };

        setMessages((prev) => [...prev, assistantMsg]);

        // Voice output if voice mode is on
        if (voiceMode && assistantMsg.content) {
          playAudio(assistantMsg.content);
        }
      } catch (err) {
        console.error("Chat request failed:", err);

        const message =
          err instanceof Error &&
          (err.message.includes("Failed to fetch") || err.message.includes("500"))
            ? "Backend service is unavailable. Start the backend on port 8001 and try again."
            : "Sorry, I encountered an error processing your request. Please try again.";

        const errorMsg: ChatMessage = {
          id: `err_${Date.now()}`,
          role: "assistant",
          content: message,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
      }
    },
    [voiceMode, playAudio],
  );

  // ── Voice input result ──
  const handleVoiceResult = useCallback(
    (text: string) => {
      handleSend(text);
    },
    [handleSend],
  );

  return (
    <>
      <Head>
        <title>JARVIS — Personal AI Assistant</title>
        <meta name="description" content="JARVIS AI Personal Assistant" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="flex flex-col h-screen bg-jarvis-bg">
        <Header
          voiceMode={voiceMode}
          onToggleVoice={() => setVoiceMode((v) => !v)}
          connected={connected}
        />

        <ChatWindow messages={messages} isLoading={isLoading} />

        <ChatInput
          onSend={handleSend}
          onVoiceResult={handleVoiceResult}
          disabled={isLoading}
          voiceMode={voiceMode}
        />
      </div>
    </>
  );
}
