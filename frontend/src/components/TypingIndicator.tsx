import React from "react";

export default function TypingIndicator() {
  return (
    <div className="flex justify-start mb-4">
      <div className="w-10 h-10 rounded flex flex-shrink-0 items-center justify-center mr-4 mt-1">
        <img src="/logo.png" alt="Assistant" className="w-10 h-10 object-contain" />
      </div>
      <div className="bg-jarvis-surface border border-jarvis-border rounded-[14px] rounded-bl-sm px-4 py-3 shadow-[0_2px_8px_rgba(0,0,0,0.04)]">
        <div className="flex items-center gap-2.5">
          <span className="text-[13px] text-jarvis-muted font-medium">Thinking</span>
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-jarvis-accent-primary/80 animate-bounce [animation-delay:-0.25s]" />
            <span className="w-1.5 h-1.5 rounded-full bg-jarvis-accent-primary/80 animate-bounce [animation-delay:-0.125s]" />
            <span className="w-1.5 h-1.5 rounded-full bg-jarvis-accent-primary/80 animate-bounce" />
          </div>
        </div>
      </div>
    </div>
  );
}
