import React, { useCallback, useEffect, useState } from "react";
import {
  CpuChipIcon,
  LightBulbIcon,
  SparklesIcon,
  ChatBubbleLeftIcon,
} from "@heroicons/react/24/outline";
import { getMemories } from "@/services/api";
import type { MemoriesResponse } from "@/types";

export default function MemoryViewer() {
  const [data, setData] = useState<MemoriesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<
    "facts" | "patterns" | "knowledge" | "history"
  >("facts");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const memories = await getMemories();
      setData(memories);
    } catch {
      // Unavailable
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const sections = [
    {
      id: "facts" as const,
      label: "Learned Facts",
      icon: LightBulbIcon,
      count: data?.learned_facts.length ?? 0,
    },
    {
      id: "patterns" as const,
      label: "Behavior Patterns",
      icon: SparklesIcon,
      count: data?.behavior_patterns.length ?? 0,
    },
    {
      id: "knowledge" as const,
      label: "Knowledge",
      icon: CpuChipIcon,
      count: data?.knowledge_entries.length ?? 0,
    },
    {
      id: "history" as const,
      label: "Conversations",
      icon: ChatBubbleLeftIcon,
      count: data?.conversation_history.length ?? 0,
    },
  ];

  return (
    <div className="flex-1 flex flex-col h-full bg-transparent p-6 md:p-10 lg:p-14 overflow-hidden relative">
      {/* Header */}
      <div className="mb-8 z-10">
        <h2 className="text-3xl font-light text-jarvis-text tracking-wide drop-shadow-sm">
          Memory Viewer
        </h2>
        <p className="text-jarvis-muted mt-2 text-[14px] font-light tracking-wide">
          What JARVIS remembers about you — full transparency
        </p>
      </div>

      {/* Section Tabs */}
      <div className="flex gap-2 mb-6 z-10 flex-wrap">
        {sections.map((s) => {
          const Icon = s.icon;
          const isActive = activeSection === s.id;
          return (
            <button
              key={s.id}
              onClick={() => setActiveSection(s.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-full text-[13px] font-medium transition-all duration-300 ${
                isActive
                  ? "bg-jarvis-accent-primary text-white shadow-halo-cyan"
                  : "bg-jarvis-surface border border-jarvis-border text-jarvis-muted hover:text-jarvis-text hover:bg-jarvis-panel"
              }`}
            >
              <Icon className="w-4 h-4" />
              {s.label}
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-[4px] ${
                  isActive ? "bg-white/20" : "bg-jarvis-border text-jarvis-text"
                }`}
              >
                {s.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto z-10 pb-8">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="text-jarvis-muted text-sm">Loading memories...</div>
          </div>
        ) : !data ? (
          <div className="flex items-center justify-center h-40 text-jarvis-muted text-sm">
            Could not load memories.
          </div>
        ) : (
          <>
            {/* Learned Facts */}
            {activeSection === "facts" && (
              <div className="space-y-3">
                {data.learned_facts.length === 0 ? (
                  <p className="text-jarvis-muted text-sm p-4">
                    No learned facts yet. JARVIS learns about you through conversations.
                  </p>
                ) : (
                  data.learned_facts.map((fact, i) => (
                    <div
                      key={i}
                      className="p-4 rounded-[8px] bg-jarvis-surface border border-transparent hover:border-jarvis-border shadow-sm transition-all duration-200"
                    >
                      <p className="text-[14px] text-jarvis-text leading-relaxed">
                        {fact.summary}
                      </p>
                      <div className="flex items-center gap-3 mt-2">
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-jarvis-accent-primary/10 text-jarvis-accent-primary font-medium">
                          {fact.topic}
                        </span>
                        <span className="text-[10px] text-jarvis-muted">
                          Confidence: {(fact.confidence * 100).toFixed(0)}%
                        </span>
                        {fact.captured_at && (
                          <span className="text-[10px] text-jarvis-muted">
                            {new Date(fact.captured_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Behavior Patterns */}
            {activeSection === "patterns" && (
              <div className="space-y-3">
                {data.behavior_patterns.length === 0 ? (
                  <p className="text-jarvis-muted text-sm p-4">
                    No behavior patterns detected yet. Use JARVIS more and patterns will emerge.
                  </p>
                ) : (
                  data.behavior_patterns.map((bp, i) => (
                    <div
                      key={i}
                      className="p-4 rounded-[8px] bg-jarvis-surface border border-transparent hover:border-jarvis-border shadow-sm transition-all duration-200"
                    >
                      <p className="text-[14px] text-jarvis-text leading-relaxed">
                        {bp.content}
                      </p>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Knowledge */}
            {activeSection === "knowledge" && (
              <div className="space-y-3">
                {data.knowledge_entries.length === 0 ? (
                  <p className="text-jarvis-muted text-sm p-4">
                    No knowledge entries. Add knowledge from the Knowledge Base page.
                  </p>
                ) : (
                  data.knowledge_entries.map((ke, i) => (
                    <div
                      key={i}
                      className="p-4 rounded-[8px] bg-jarvis-surface border border-transparent hover:border-jarvis-border shadow-sm transition-all duration-200"
                    >
                      <p className="text-[14px] text-jarvis-text leading-relaxed">
                        {ke.content}
                      </p>
                      <div className="flex items-center gap-3 mt-2">
                        {ke.topic && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-jarvis-accent-cyan/10 text-jarvis-accent-cyan font-medium">
                            {ke.topic}
                          </span>
                        )}
                        {ke.source_filename && (
                          <span className="text-[10px] text-jarvis-muted">
                            {ke.source_filename}
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Conversation History */}
            {activeSection === "history" && (
              <div className="space-y-2">
                {data.conversation_history.length === 0 ? (
                  <p className="text-jarvis-muted text-sm p-4">
                    No conversation history available.
                  </p>
                ) : (
                  data.conversation_history.map((msg, i) => (
                    <div
                      key={i}
                      className={`p-3 rounded-[14px] ${
                        msg.role === "user"
                          ? "bg-jarvis-accent-primary/5 border border-jarvis-accent-primary/10 ml-8"
                          : "bg-jarvis-surface border border-transparent hover:border-jarvis-border mr-8"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-medium text-jarvis-muted uppercase tracking-wider">
                          {msg.role}
                        </span>
                        <span className="text-[10px] text-jarvis-muted/60">
                          {new Date(msg.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-[13px] text-jarvis-text leading-relaxed">
                        {msg.content.length > 300
                          ? `${msg.content.slice(0, 300)}...`
                          : msg.content}
                      </p>
                    </div>
                  ))
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
