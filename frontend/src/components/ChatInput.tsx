import React, { useCallback, useEffect, useRef, useState } from "react";
import { Mic, MicOff, Send } from "lucide-react";

type SpeechRecognitionCtor = new () => SpeechRecognition;

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

interface SpeechRecognitionEvent {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      [index: number]: { transcript: string };
    };
  };
}

interface SpeechRecognitionErrorEvent {
  error: string;
}

declare global {
  interface Window {
    webkitSpeechRecognition?: SpeechRecognitionCtor;
    SpeechRecognition?: SpeechRecognitionCtor;
  }
}

interface ChatInputProps {
  onSend: (text: string) => void;
  onVoiceResult: (text: string) => void;
  onVoicePartial?: (text: string) => void;
  onVoiceFinal?: (text: string) => void;
  onVoiceAudioChunk?: (audioBase64: string, mimeType: string) => void;
  onVoiceAudioStop?: () => void;
  onVoiceError: (message: string) => void;
  onListeningChange: (isListening: boolean) => void;
  onTranscribingChange: (isTranscribing: boolean) => void;
  disabled: boolean;
  voiceMode: boolean;
}

export default function ChatInput({
  onSend,
  onVoiceResult,
  onVoicePartial,
  onVoiceFinal,
  onVoiceAudioChunk,
  onVoiceAudioStop,
  onVoiceError,
  onListeningChange,
  onTranscribingChange,
  disabled,
  voiceMode,
}: ChatInputProps) {
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const speechRecognition = useRef<SpeechRecognition | null>(null);
  const recognitionTranscript = useRef("");
  const voiceInputMode = useRef<"speech-recognition" | "media-recorder" | null>(null);
  const chunks = useRef<Blob[]>([]);

  const blobToBase64 = useCallback(async (blob: Blob): Promise<string> => {
    const arr = new Uint8Array(await blob.arrayBuffer());
    let binary = "";
    for (let i = 0; i < arr.length; i += 1) {
      binary += String.fromCharCode(arr[i]);
    }
    return btoa(binary);
  }, []);

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

  const startRecording = useCallback(async () => {
    const SpeechRecognitionAPI =
      (typeof window !== "undefined" &&
        (window.SpeechRecognition || window.webkitSpeechRecognition)) ||
      null;

    if (SpeechRecognitionAPI) {
      try {
        const recognizer = new SpeechRecognitionAPI();
        recognizer.continuous = false;
        recognizer.interimResults = true;
        recognizer.lang = "en-US";

        recognitionTranscript.current = "";
        voiceInputMode.current = "speech-recognition";

        recognizer.onresult = (event: SpeechRecognitionEvent) => {
          let transcript = "";
          for (let i = event.resultIndex; i < event.results.length; i += 1) {
            transcript += event.results[i][0].transcript;
          }
          recognitionTranscript.current = transcript.trim();
          if (recognitionTranscript.current) {
            onVoicePartial?.(recognitionTranscript.current);
          }
        };

        recognizer.onerror = (event: SpeechRecognitionErrorEvent) => {
          onVoiceError(`Voice recognition error: ${event.error}`);
        };

        recognizer.onend = () => {
          const transcript = recognitionTranscript.current;
          setRecording(false);
          onListeningChange(false);
          onTranscribingChange(false);

          if (transcript) {
            if (onVoiceFinal) {
              onVoiceFinal(transcript);
            } else {
              onVoiceResult(transcript);
            }
          } else {
            onVoiceError("No speech detected. Please try again and speak clearly.");
          }

          recognitionTranscript.current = "";
          speechRecognition.current = null;
          voiceInputMode.current = null;
        };

        speechRecognition.current = recognizer;
        recognizer.start();
        setRecording(true);
        onListeningChange(true);
        onTranscribingChange(false);
        return;
      } catch {
        onVoiceError("Browser voice recognition failed. Falling back to audio upload.");
      }
    }

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        onVoiceError("Microphone is not supported in this browser.");
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      voiceInputMode.current = "media-recorder";
      chunks.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };

      const useSocketAudioStreaming = Boolean(onVoiceAudioChunk && onVoiceAudioStop);

      if (useSocketAudioStreaming) {
        recorder.ondataavailable = async (e) => {
          if (!e.data || e.data.size === 0) return;
          try {
            const encoded = await blobToBase64(e.data);
            onVoiceAudioChunk?.(encoded, recorder.mimeType || "audio/webm");
          } catch {
            onVoiceError("Failed to stream audio chunk.");
          }
        };

        recorder.onstop = () => {
          stream.getTracks().forEach((t) => t.stop());
          setRecording(false);
          onListeningChange(false);
          onTranscribingChange(true);
          onVoiceAudioStop?.();
          voiceInputMode.current = null;
        };

        recorder.start(300);
        mediaRecorder.current = recorder;
        setRecording(true);
        onListeningChange(true);
        return;
      }

      recorder.onstop = async () => {
        const mimeType = recorder.mimeType || "audio/webm";
        const extension = mimeType.includes("ogg") ? "ogg" : "webm";
        const blob = new Blob(chunks.current, { type: mimeType });
        stream.getTracks().forEach((t) => t.stop());
        setRecording(false);
        onListeningChange(false);
        onTranscribingChange(true);

        try {
          const form = new FormData();
          form.append("file", blob, `recording.${extension}`);
          const res = await fetch("/api/voice-to-text", {
            method: "POST",
            body: form,
          });

          if (!res.ok) {
            const detailText = await res.text();
            let detail = detailText;
            try {
              const parsed = JSON.parse(detailText) as { detail?: string };
              detail = parsed.detail || detailText;
            } catch {
              // Keep raw text when response is not JSON
            }
            throw new Error(detail || "Voice recognition failed");
          }

          const data = await res.json();
          if (data.text) {
            if (onVoiceFinal) {
              onVoiceFinal(data.text as string);
            } else {
              onVoiceResult(data.text as string);
            }
          } else {
            onVoiceError("No speech detected. Please speak again and stop recording.");
          }

        } catch (err) {
          const message = err instanceof Error ? err.message : "Voice recognition failed.";
          onVoiceError(message);
        } finally {
          onTranscribingChange(false);
          voiceInputMode.current = null;
        }
      };

      recorder.start();
      mediaRecorder.current = recorder;
      setRecording(true);
      onListeningChange(true);
    } catch {
      onVoiceError("Microphone permission denied or recording failed.");
      onListeningChange(false);
      onTranscribingChange(false);
    }
  }, [
    onVoiceResult,
    onVoicePartial,
    onVoiceFinal,
    onVoiceAudioChunk,
    onVoiceAudioStop,
    onVoiceError,
    onListeningChange,
    onTranscribingChange,
    blobToBase64,
  ]);

  const stopRecording = useCallback(() => {
    if (voiceInputMode.current === "speech-recognition" && speechRecognition.current) {
      speechRecognition.current.stop();
      return;
    }

    if (mediaRecorder.current && mediaRecorder.current.state !== "inactive") {
      mediaRecorder.current.stop();
    }
    setRecording(false);
    onListeningChange(false);
  }, [onListeningChange]);

  useEffect(() => {
    if (!voiceMode && recording) {
      stopRecording();
    }
  }, [voiceMode, recording, stopRecording]);

  return (
    <div className="pb-8 px-4 md:px-12 lg:px-24">
      <div className="max-w-[840px] mx-auto flex items-end gap-3 bg-jarvis-surface border border-jarvis-border rounded-[24px] pl-5 pr-2 py-2 shadow-panel transition-all duration-300 ring-2 ring-transparent focus-within:ring-[#0078D4]/50 hover:border-[#0078D4]/30">

        {voiceMode && (
          <button
            onClick={recording ? stopRecording : startRecording}
            disabled={disabled}
            className={`
              p-2 rounded-[18px] transition-all duration-300 shrink-0 outline-none
              ${recording
                ? "bg-jarvis-danger/10 text-jarvis-danger hover:bg-jarvis-danger/20"
                : "text-jarvis-muted hover:bg-jarvis-surface hover:text-jarvis-text"
              }
              disabled:opacity-40
            `}
          >
            {recording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>
        )}

        <div className="flex-1 relative">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Ask Jarvis anything... ➤"
            rows={1}
            className="
              w-full resize-none bg-transparent border-none
              px-0 py-2.5 text-[15px] text-jarvis-text placeholder:text-jarvis-muted/70
              focus:outline-none focus:ring-0
              disabled:opacity-40
              max-h-32 overflow-y-auto font-normal my-auto
            "
            style={{ minHeight: "24px" }}
          />
        </div>

        <button
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="
            p-2.5 rounded-full bg-transparent text-jarvis-muted transition-all duration-150 shrink-0 outline-none
            hover:bg-jarvis-panel hover:text-jarvis-text active:scale-95
            disabled:opacity-40 disabled:hover:bg-transparent disabled:text-jarvis-muted
          "
        >
          <Send className="w-[20px] h-[20px]" />
        </button>
      </div>

      {voiceMode && recording && (
        <p className="mx-auto mt-2 max-w-3xl px-2 text-xs text-jarvis-muted">
          Listening... tap mic again to stop and send.
        </p>
      )}
    </div>
  );
}
