import React from "react";

export default function TypingIndicator() {
  return (
    <div className="flex justify-start mb-4">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-jarvis-accent to-purple-500 flex items-center justify-center text-white text-xs font-bold mr-3 mt-1 shrink-0">
        J
      </div>
      <div className="bg-jarvis-assistant border border-jarvis-border rounded-2xl rounded-bl-md px-5 py-3">
        <div className="flex gap-1.5">
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
        </div>
      </div>
    </div>
  );
}
