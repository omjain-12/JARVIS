import React, { useCallback, useRef, useState } from "react";
import { Mic, MicOff, Send } from "lucide-react";

interface ChatInputProps {
  onSend: (text: string) => void;
  onVoiceResult: (text: string) => void;
  disabled: boolean;
  voiceMode: boolean;
}

export default function ChatInput({
  onSend,
  onVoiceResult,
  disabled,
  voiceMode,
}: ChatInputProps) {
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  }, [text, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── Microphone recording ──

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunks.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };

      recorder.onstop = async () => {
        const blob = new Blob(chunks.current, { type: "audio/wav" });
        stream.getTracks().forEach((t) => t.stop());

        // Send to backend for STT
        try {
          const form = new FormData();
          form.append("file", blob, "recording.wav");
          const res = await fetch("/api/voice-to-text", {
            method: "POST",
            body: form,
          });
          if (res.ok) {
            const data = await res.json();
            if (data.text) {
              onVoiceResult(data.text);
            }
          }
        } catch {
          // Fallback: voice failed silently, user can type instead
        }
      };

      recorder.start();
      mediaRecorder.current = recorder;
      setRecording(true);
    } catch {
      // Microphone permission denied or not available
    }
  }, [onVoiceResult]);

  const stopRecording = useCallback(() => {
    if (mediaRecorder.current && mediaRecorder.current.state !== "inactive") {
      mediaRecorder.current.stop();
    }
    setRecording(false);
  }, []);

  return (
    <div className="border-t border-jarvis-border bg-jarvis-surface/80 backdrop-blur-sm px-4 py-3 md:px-8 lg:px-16">
      <div className="flex items-end gap-2 max-w-4xl mx-auto">
        {/* Voice button */}
        {voiceMode && (
          <button
            onClick={recording ? stopRecording : startRecording}
            disabled={disabled}
            className={`
              p-3 rounded-xl transition-colors shrink-0
              ${
                recording
                  ? "bg-red-500/20 text-red-400 hover:bg-red-500/30"
                  : "bg-jarvis-border text-jarvis-muted hover:text-jarvis-text hover:bg-jarvis-border/80"
              }
              disabled:opacity-40 disabled:cursor-not-allowed
            `}
            title={recording ? "Stop recording" : "Start recording"}
          >
            {recording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>
        )}

        {/* Text input */}
        <div className="flex-1 relative">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Type a message…"
            rows={1}
            className="
              w-full resize-none rounded-xl bg-jarvis-bg border border-jarvis-border
              px-4 py-3 text-sm text-jarvis-text placeholder:text-jarvis-muted
              focus:outline-none focus:ring-2 focus:ring-jarvis-accent/50 focus:border-jarvis-accent
              disabled:opacity-40 disabled:cursor-not-allowed
              max-h-32 overflow-y-auto
            "
            style={{ minHeight: "44px" }}
          />
        </div>

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="
            p-3 rounded-xl bg-jarvis-accent text-white transition-colors shrink-0
            hover:bg-jarvis-accent-hover
            disabled:opacity-40 disabled:cursor-not-allowed
          "
          title="Send message"
        >
          <Send className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
