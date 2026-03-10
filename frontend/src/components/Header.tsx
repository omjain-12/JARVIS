import React, { useEffect, useState } from "react";
import { useTheme } from "next-themes";

interface HeaderProps {
  voiceMode: boolean;
  isListening: boolean;
  isTranscribing: boolean;
  isThinking: boolean;
  isSpeaking: boolean;
  liveTranscript: string;
  onToggleVoice: () => void;
  connected: boolean;
}

export default function Header({
  voiceMode,
  isListening,
  isTranscribing,
  isThinking,
  isSpeaking,
  liveTranscript,
  onToggleVoice,
  connected,
}: HeaderProps) {
  const { theme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const logoSrc = !mounted ? "/logo.png" : theme === "dark" ? "/black_logo.png" : "/white_logo.png";

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-jarvis-border bg-jarvis-surface/80 backdrop-blur-sm">
      {/* Logo & title */}
      <div className="flex items-center gap-3">
        <div className="h-20 w-20 md:h-[40px] md:w-[88px] flex items-center justify-center">
          <img
            src={logoSrc}
            alt="Logo"
            className="h-full w-full object-contain"
          />
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4">
        {voiceMode && isListening && (
          <div className="flex items-center gap-2 rounded-full border border-red-400/30 bg-red-500/10 px-3 py-1.5 text-xs text-red-300">
            <span className="h-2 w-2 animate-pulse rounded-full bg-red-400" />
            Listening...
          </div>
        )}

        {voiceMode && !isListening && isTranscribing && (
          <div className="flex items-center gap-2 rounded-full border border-sky-400/30 bg-sky-500/10 px-3 py-1.5 text-xs text-sky-300">
            <span className="h-2 w-2 animate-pulse rounded-full bg-sky-400" />
            Transcribing...
          </div>
        )}

        {voiceMode && !isListening && !isTranscribing && isThinking && (
          <div className="flex items-center gap-2 rounded-full border border-amber-400/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-300">
            <span className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
            Thinking...
          </div>
        )}

        {voiceMode && !isListening && !isTranscribing && isSpeaking && (
          <div className="flex items-center gap-2 rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-300">
            <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
            Responding...
          </div>
        )}

        {voiceMode && isListening && liveTranscript && (
          <div className="max-w-[240px] truncate text-xs text-jarvis-muted" title={liveTranscript}>
            {liveTranscript}
          </div>
        )}

        {/* Connection indicator */}
        <div className="flex items-center gap-2 text-[13px] text-jarvis-text opacity-90 font-medium bg-[#161C28]/60 backdrop-blur-lg px-3 py-1.5 rounded-[12px] border border-white/5">
          <span
            className={`w-2 h-2 rounded-full ${
              connected ? "bg-green-400 animate-pulse shadow-[0_0_8px_rgba(74,222,128,0.8)]" : "bg-red-400"
            }`}
          />
          {connected ? "Connected" : "Offline"}
        </div>

        {/* Voice mode toggle */}
        <button
          onClick={onToggleVoice}
          className={`
            px-3 py-1.5 text-xs font-medium rounded-full transition-colors
            ${
              voiceMode
                ? "bg-jarvis-accent text-white"
                : "bg-jarvis-border text-jarvis-muted hover:text-jarvis-text"
            }
          `}
        >
          Voice {voiceMode ? "ON" : "OFF"}
        </button>
      </div>
    </header>
  );
}
