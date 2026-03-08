import React, { useEffect, useRef } from "react";
import type { ChatMessage } from "@/types";
import ChatBubble from "./ChatBubble";
import TypingIndicator from "./TypingIndicator";

interface ChatWindowProps {
  messages: ChatMessage[];
  isLoading: boolean;
}

export default function ChatWindow({ messages, isLoading }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8 lg:px-16">
      {messages.length === 0 && !isLoading && (
        <div className="flex flex-col items-center justify-center h-full text-center">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-jarvis-accent to-purple-500 flex items-center justify-center text-white text-2xl font-bold mb-4">
            J
          </div>
          <h2 className="text-xl font-semibold text-jarvis-text mb-2">
            Hello! I&apos;m JARVIS
          </h2>
          <p className="text-jarvis-muted text-sm max-w-md">
            Your personal AI assistant. Ask me anything, set reminders, track
            habits, or manage your tasks.
          </p>
        </div>
      )}

      {messages.map((msg) => (
        <ChatBubble key={msg.id} message={msg} />
      ))}

      {isLoading && <TypingIndicator />}

      <div ref={bottomRef} />
    </div>
  );
}
