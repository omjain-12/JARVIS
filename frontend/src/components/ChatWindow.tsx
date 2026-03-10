import React, { useEffect, useRef } from "react";
import type { ChatMessage } from "@/types";
import ChatBubble from "./ChatBubble";
import TypingIndicator from "./TypingIndicator";

interface ChatWindowProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onUpdateMessage?: (id: string, updates: Partial<ChatMessage>) => void;
}

export default function ChatWindow({ messages, isLoading, onUpdateMessage }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto px-4 pt-8 pb-40 md:px-12 lg:px-24">
      {messages.length === 0 && !isLoading && (
        <div className="flex flex-col items-center justify-center h-full text-center mt-[-10vh]">
          <div className="w-24 h-24 rounded-2xl flex items-center justify-center mb-6 shadow-lg shadow-jarvis-accent-primary/20">
            <img
              src="/logo.png"
              alt="Logo"
              className="w-24 h-24 object-contain"
            />
          </div>
          <h2 className="text-2xl font-semibold text-jarvis-text tracking-tight mb-3">
            How can I help you today?
          </h2>
          <p className="text-jarvis-muted text-sm max-w-sm">
            I can manage your calendar, track your habits, save knowledge notes, or simply chat.
          </p>
        </div>
      )}

      <div className="space-y-6 max-w-3xl mx-auto">
        {messages.map((msg) => (
          <ChatBubble key={msg.id} message={msg} onUpdateMessage={onUpdateMessage} />
        ))}
        {isLoading && <TypingIndicator />}
        <div ref={bottomRef} className="h-4" />
      </div>
    </div>
  );
}
