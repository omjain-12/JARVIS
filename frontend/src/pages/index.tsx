import React, { useCallback, useEffect, useRef, useState } from "react";
import Head from "next/head";
import Header from "@/components/Header";
import ChatWindow from "@/components/ChatWindow";
import ChatInput from "@/components/ChatInput";
import Sidebar from "@/components/Sidebar";
import RightPanel from "@/components/RightPanel";
import CalendarWidget from "@/components/CalendarWidget";
import TasksDashboard from "@/components/TasksDashboard";
import ContactsManager from "@/components/ContactsManager";
import KnowledgeBase from "@/components/KnowledgeBase";
import MemoryViewer from "@/components/MemoryViewer";
import CommsWidget from "@/components/CommsWidget";
import { sendMessage, getHealth, textToVoice } from "@/services/api";
import { LiveTalkClient, type LiveTalkEvent } from "@/services/liveTalk";
import type { ChatMessage, LiveVoiceState } from "@/types";

const USER_ID = "demo_user";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [liveState, setLiveState] = useState<LiveVoiceState>("idle");
  const [liveTranscript, setLiveTranscript] = useState("");
  const [connected, setConnected] = useState(false);
  const [activeTab, setActiveTab] = useState("home");
  const sessionId = useRef(`session_${Date.now()}`);
  const liveClientRef = useRef<LiveTalkClient | null>(null);
  const streamingAssistantIdRef = useRef<string | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const receivedAudioChunkRef = useRef(false);
  const finalTextRef = useRef("");

  // ── Refs to break stale closures ──
  const liveStateRef = useRef<LiveVoiceState>("idle");
  const isListeningRef = useRef(false);
  const isTranscribingRef = useRef(false);

  // Keep refs in sync with state
  useEffect(() => { liveStateRef.current = liveState; }, [liveState]);
  useEffect(() => { isListeningRef.current = isListening; }, [isListening]);
  useEffect(() => { isTranscribingRef.current = isTranscribing; }, [isTranscribing]);

  useEffect(() => {
    getHealth()
      .then(() => setConnected(true))
      .catch(() => setConnected(false));
  }, []);

  /** Update a specific message by ID (used by confirmation cards). */
  const handleUpdateMessage = useCallback((id: string, updates: Partial<ChatMessage>) => {
    setMessages((prev) =>
      prev.map((msg) => (msg.id === id ? { ...msg, ...updates } : msg))
    );
  }, []);

  const stopCurrentAudio = useCallback(() => {
    // Stop HTML audio
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.currentTime = 0;
      currentAudioRef.current = null;
    }
    // Stop browser TTS
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }, []);

  /** Speak text using the browser's built-in speech synthesis (no server needed). */
  const speakWithBrowserTTS = useCallback((text: string) => {
    if (!text.trim()) return;
    if (typeof window === "undefined" || !window.speechSynthesis) return;

    window.speechSynthesis.cancel(); // stop any ongoing utterance

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 0.98;
    utterance.pitch = 0.88;

    // Try to pick a natural-sounding male English voice first.
    const voices = window.speechSynthesis.getVoices();
    const preferredNames = ["Andrew", "Guy", "Davis", "Ryan", "David", "James", "George"];
    const preferred = preferredNames
      .map((name) => voices.find((v) => v.lang.startsWith("en") && v.name.includes(name)))
      .find((v) => Boolean(v))
      || voices.find((v) => v.lang.startsWith("en") && /male|guy/i.test(v.name))
      || voices.find((v) => v.lang.startsWith("en"));
    if (preferred) utterance.voice = preferred;

    setLiveState("speaking");
    utterance.onend = () => {
      setLiveState("idle");
    };
    utterance.onerror = () => {
      setLiveState("idle");
    };

    window.speechSynthesis.speak(utterance);
  }, []);

  const playAudio = useCallback(async (text: string) => {
    try {
      const blob = await textToVoice(text);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      currentAudioRef.current = audio;
      setLiveState("speaking");
      audio.play();
      audio.onended = () => {
        URL.revokeObjectURL(url);
        currentAudioRef.current = null;
        setLiveState("idle");
      };
    } catch {
      // Azure TTS failed — fall back to browser TTS
      speakWithBrowserTTS(text);
    }
  }, [speakWithBrowserTTS]);

  const appendAssistantDelta = useCallback((delta: string) => {
    setMessages((prev) => {
      const msgId = streamingAssistantIdRef.current;
      if (!msgId) {
        const newId = `asst_stream_${Date.now()}`;
        streamingAssistantIdRef.current = newId;
        return [
          ...prev,
          {
            id: newId,
            role: "assistant" as const,
            content: delta,
            timestamp: Date.now(),
          },
        ];
      }

      return prev.map((msg) =>
        msg.id === msgId ? { ...msg, content: `${msg.content}${delta}` } : msg,
      );
    });
  }, []);

  const finalizeAssistantMessage = useCallback((text: string) => {
    if (!text.trim()) {
      streamingAssistantIdRef.current = null;
      return;
    }

    setMessages((prev) => {
      const msgId = streamingAssistantIdRef.current;
      if (!msgId) {
        return [
          ...prev,
          {
            id: `asst_${Date.now()}`,
            role: "assistant" as const,
            content: text,
            timestamp: Date.now(),
          },
        ];
      }

      return prev.map((msg) =>
        msg.id === msgId ? { ...msg, content: text } : msg,
      );
    });

    streamingAssistantIdRef.current = null;
  }, []);

  const playLiveAudioChunk = useCallback((audioBase64: string, mimeType: string) => {
    try {
      const binary = atob(audioBase64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
      }

      const blob = new Blob([bytes], { type: mimeType || "audio/wav" });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      currentAudioRef.current = audio;
      setLiveState("speaking");
      audio.play();
      audio.onended = () => {
        URL.revokeObjectURL(url);
        currentAudioRef.current = null;
        setLiveState("idle");
      };
    } catch {
      setLiveState("idle");
    }
  }, []);

  // ── Live event handler as a stable ref — never causes WS reconnect ──
  const handleLiveEventRef = useRef<((event: LiveTalkEvent) => void) | null>(null);

  useEffect(() => {
    handleLiveEventRef.current = (event: LiveTalkEvent) => {
      switch (event.type) {
        case "session.ready":
          return;
        case "stt.final":
          setIsTranscribing(false);
          setLiveTranscript("");
          setMessages((prev) => [
            ...prev,
            {
              id: `user_${Date.now()}`,
              role: "user",
              content: event.text,
              timestamp: Date.now(),
            },
          ]);
          setLiveState("thinking");
          receivedAudioChunkRef.current = false;
          finalTextRef.current = "";
          return;
        case "assistant.thinking":
          setIsTranscribing(false);
          setLiveState("thinking");
          receivedAudioChunkRef.current = false;
          finalTextRef.current = "";
          return;
        case "assistant.text.delta":
          // Transition to "speaking" once text starts streaming in
          setLiveState((prev) => prev === "thinking" ? "speaking" : prev);
          appendAssistantDelta(event.text);
          return;
        case "assistant.text.final":
          finalizeAssistantMessage(event.text);
          finalTextRef.current = event.text;
          return;
        case "assistant.audio.chunk":
          receivedAudioChunkRef.current = true;
          playLiveAudioChunk(event.audio_base64, event.mime_type);
          return;
        case "assistant.interrupted":
          setLiveState("idle");
          streamingAssistantIdRef.current = null;
          return;
        case "assistant.done":
          // If backend didn't send audio, speak via browser TTS
          if (!receivedAudioChunkRef.current && finalTextRef.current) {
            speakWithBrowserTTS(finalTextRef.current);
          } else {
            setLiveState((prev) => prev === "speaking" ? prev : "idle");
          }
          finalTextRef.current = "";
          receivedAudioChunkRef.current = false;
          return;
        case "error":
          setIsTranscribing(false);
          setLiveState("idle");
          setMessages((prev) => [
            ...prev,
            {
              id: `live_err_${Date.now()}`,
              role: "assistant",
              content: event.message,
              timestamp: Date.now(),
            },
          ]);
          return;
        default:
      }
    };
  }, [appendAssistantDelta, finalizeAssistantMessage, playLiveAudioChunk, speakWithBrowserTTS]);

  // ── WebSocket lifecycle — only depends on voiceMode, NOT on callbacks ──
  useEffect(() => {
    if (!voiceMode) {
      liveClientRef.current?.disconnect();
      liveClientRef.current = null;
      setLiveState("idle");
      setLiveTranscript("");
      return;
    }

    const client = new LiveTalkClient({
      onEvent: (event) => {
        // Delegate to the ref so updates don't cause reconnect
        handleLiveEventRef.current?.(event);
      },
      onOpen: () => {
        client.startSession(USER_ID, sessionId.current);
      },
      onError: (message) => {
        setMessages((prev) => [
          ...prev,
          {
            id: `live_socket_err_${Date.now()}`,
            role: "assistant",
            content: message,
            timestamp: Date.now(),
          },
        ]);
      },
    });

    liveClientRef.current = client;
    client.connect();

    return () => {
      client.disconnect();
      liveClientRef.current = null;
    };
  }, [voiceMode]);  // ← only voiceMode — stable connection!

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
        if (!isListeningRef.current && !isTranscribingRef.current) {
          setLiveState("idle");
        }
      }
    },
    [voiceMode, playAudio],
  );

  const handleVoiceResult = useCallback(
    (text: string) => {
      handleSend(text);
    },
    [handleSend],
  );

  const handleLiveVoiceFinal = useCallback(
    (text: string) => {
      if (!text.trim()) return;

      setLiveTranscript("");

      const userMsg: ChatMessage = {
        id: `user_${Date.now()}`,
        role: "user",
        content: text,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);

      if (liveClientRef.current?.isConnected()) {
        receivedAudioChunkRef.current = false;
        finalTextRef.current = "";
        liveClientRef.current.sendUtterance(text);
        setLiveState("thinking");
      } else {
        handleSend(text);
      }
    },
    [handleSend],
  );

  const handleVoicePartial = useCallback((text: string) => {
    setLiveTranscript(text);
  }, []);

  const handleVoiceError = useCallback((message: string) => {
    setIsTranscribing(false);
    setLiveState("idle");
    const errorMsg: ChatMessage = {
      id: `voice_err_${Date.now()}`,
      role: "assistant",
      content: message,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, errorMsg]);
  }, []);

  const handleListeningChange = useCallback((next: boolean) => {
    setIsListening(next);
    if (next) {
      setLiveState("listening");
      if (liveClientRef.current?.isConnected()) {
        liveClientRef.current.interrupt();
      }
      stopCurrentAudio();
      return;
    }

    if (!isTranscribingRef.current) {
      setLiveState("idle");
    }
  }, [stopCurrentAudio]);

  const handleVoiceAudioChunk = useCallback((audioBase64: string, mimeType: string) => {
    if (!liveClientRef.current?.isConnected()) return;
    liveClientRef.current.sendAudioChunk(audioBase64, mimeType);
  }, []);

  const handleVoiceAudioStop = useCallback(() => {
    if (!liveClientRef.current?.isConnected()) {
      setIsTranscribing(false);
      return;
    }
    liveClientRef.current.stopAudioInput();
  }, []);

  const handleTranscribingChange = useCallback((next: boolean) => {
    setIsTranscribing(next);
    if (next) {
      setLiveState("transcribing");
      return;
    }
    if (!isListeningRef.current) {
      setLiveState((prev) => prev === "transcribing" ? "idle" : prev);
    }
  }, []);

  return (
    <>
      <Head>
        <title>JARVIS</title>
        <meta name="description" content="JARVIS AI Personal Assistant" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="flex h-screen overflow-hidden font-sans selection:bg-jarvis-accent-primary/30 bg-jarvis-bg transition-colors duration-500">

        {/* Left Sidebar */}
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

        {/* Center Main Content Area */}
        <main className="flex-1 flex flex-col relative min-w-0 bg-transparent border-x border-jarvis-border overflow-hidden transition-all duration-200">
          {activeTab === "home" && (
            <Header
              voiceMode={voiceMode}
              isListening={isListening}
              isTranscribing={isTranscribing}
              isThinking={liveState === "thinking"}
              isSpeaking={liveState === "speaking"}
              liveTranscript={liveTranscript}
              onToggleVoice={() => setVoiceMode((v) => !v)}
              connected={connected}
            />
          )}

          {/* Dynamic Content based on Active Tab */}
          {activeTab === "home" ? (
            <div className="flex-1 flex flex-col h-full overflow-hidden relative">
              <ChatWindow messages={messages} isLoading={isLoading} onUpdateMessage={handleUpdateMessage} />

              <div className="absolute inset-x-0 bottom-0 pointer-events-none z-10 flex flex-col">
                <div className="h-40 bg-gradient-to-t from-jarvis-bg to-transparent pointer-events-none w-full" />
                <div className="pointer-events-auto bg-jarvis-bg pt-2 pb-6">
                  <ChatInput
                    onSend={handleSend}
                    onVoiceResult={handleVoiceResult}
                    onVoicePartial={handleVoicePartial}
                    onVoiceFinal={handleLiveVoiceFinal}
                    onVoiceAudioChunk={handleVoiceAudioChunk}
                    onVoiceAudioStop={handleVoiceAudioStop}
                    onVoiceError={handleVoiceError}
                    onListeningChange={handleListeningChange}
                    onTranscribingChange={handleTranscribingChange}
                    disabled={isLoading}
                    voiceMode={voiceMode}
                  />
                </div>
              </div>
            </div>
          ) : activeTab === "calendar" ? (
            <CalendarWidget />
          ) : activeTab === "tasks" ? (
            <TasksDashboard />
          ) : activeTab === "contacts" ? (
            <ContactsManager />
          ) : activeTab === "knowledge" ? (
            <KnowledgeBase />
          ) : activeTab === "memory" ? (
            <MemoryViewer />
          ) : activeTab === "communications" ? (
            <CommsWidget />
          ) : (
            <div className="flex-1 flex items-center justify-center text-jarvis-text/40 flex-col h-full">
              <div className="w-16 h-16 mb-4 rounded-2xl bg-jarvis-glass-bg border border-jarvis-glass-border flex items-center justify-center shadow-halo">
                <span className="text-2xl opacity-50">🚧</span>
              </div>
              <h3 className="text-jarvis-text/80 text-lg font-medium tracking-tight mb-2">Under Construction</h3>
            </div>
          )}
        </main>

        {/* Right Contextual Panel */}
        <RightPanel />
      </div>
    </>
  );
}
