import React from "react";
import type { ChatMessage } from "@/types";

interface ChatBubbleProps {
  message: ChatMessage;
}

export default function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      {/* Avatar */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-jarvis-accent to-purple-500 flex items-center justify-center text-white text-xs font-bold mr-3 mt-1 shrink-0">
          J
        </div>
      )}

      <div className={`max-w-[75%] ${isUser ? "order-1" : ""}`}>
        {/* Bubble */}
        <div
          className={`
            px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap break-words
            ${
              isUser
                ? "bg-jarvis-user text-white rounded-br-md"
                : "bg-jarvis-assistant text-jarvis-text border border-jarvis-border rounded-bl-md"
            }
          `}
        >
          {message.content}
        </div>

        {/* Metadata pills */}
        {!isUser && message.metadata && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {message.metadata.decision && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-jarvis-border text-jarvis-muted">
                {message.metadata.decision}
              </span>
            )}
            {message.metadata.tools_used &&
              message.metadata.tools_used.length > 0 && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300">
                  {message.metadata.tools_used.join(", ")}
                </span>
              )}
            {message.metadata.total_time_ms != null &&
              message.metadata.total_time_ms > 0 && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-jarvis-border text-jarvis-muted">
                  {Math.round(message.metadata.total_time_ms)}ms
                </span>
              )}
          </div>
        )}

        {/* Timestamp */}
        <p className={`text-[10px] text-jarvis-muted mt-1 ${isUser ? "text-right" : ""}`}>
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-jarvis-user/80 flex items-center justify-center text-white text-xs font-bold ml-3 mt-1 shrink-0">
          U
        </div>
      )}
    </div>
  );
}
