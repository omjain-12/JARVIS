import React from "react";

interface HeaderProps {
  voiceMode: boolean;
  onToggleVoice: () => void;
  connected: boolean;
}

export default function Header({ voiceMode, onToggleVoice, connected }: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-jarvis-border bg-jarvis-surface/80 backdrop-blur-sm">
      {/* Logo & title */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-jarvis-accent to-purple-500 flex items-center justify-center text-white font-bold text-sm">
          J
        </div>
        <div>
          <h1 className="text-lg font-semibold text-jarvis-text leading-tight">
            JARVIS
          </h1>
          <p className="text-xs text-jarvis-muted">Personal AI Assistant</p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4">
        {/* Connection indicator */}
        <div className="flex items-center gap-1.5 text-xs text-jarvis-muted">
          <span
            className={`w-2 h-2 rounded-full ${
              connected ? "bg-green-400" : "bg-red-400"
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
