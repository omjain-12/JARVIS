import React, { useCallback, useEffect, useState } from "react";
import {
  DocumentTextIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  XMarkIcon,
  LightBulbIcon,
} from "@heroicons/react/24/outline";
import { searchKnowledge, addKnowledge } from "@/services/api";
import type { KnowledgeEntry } from "@/types";

export default function KnowledgeBase() {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [newContent, setNewContent] = useState("");
  const [newTopic, setNewTopic] = useState("general");
  const [saving, setSaving] = useState(false);

  const loadKnowledge = useCallback(async (query = "") => {
    setLoading(true);
    try {
      const data = await searchKnowledge(query);
      setEntries(data);
    } catch {
      // Unavailable
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKnowledge();
  }, [loadKnowledge]);

  const handleSearch = () => {
    loadKnowledge(searchQuery);
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  const handleAdd = async () => {
    if (!newContent.trim()) return;
    setSaving(true);
    try {
      await addKnowledge(newContent, newTopic);
      setNewContent("");
      setNewTopic("general");
      setShowForm(false);
      loadKnowledge(searchQuery);
    } catch {
      // Failed
    } finally {
      setSaving(false);
    }
  };

  const topicColors: Record<string, string> = {
    general: "text-jarvis-accent-primary bg-jarvis-accent-primary/10",
    personal_info: "text-jarvis-accent-cyan bg-jarvis-accent-cyan/10",
    goal: "text-green-400 bg-green-400/10",
    preference: "text-yellow-400 bg-yellow-400/10",
    learning: "text-jarvis-accent-uv bg-jarvis-accent-uv/10",
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-transparent p-6 md:p-10 lg:p-14 overflow-hidden relative">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 z-10">
        <div>
          <h2 className="text-3xl font-light text-jarvis-text tracking-wide drop-shadow-sm">
            Knowledge Base
          </h2>
          <p className="text-jarvis-muted mt-2 text-[14px] font-light tracking-wide">
            Your personal knowledge stored in vector memory
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-5 py-2.5 rounded-[4px] bg-jarvis-surface border border-jarvis-border text-jarvis-text text-[13px] font-medium transition-all hover:bg-jarvis-panel"
        >
          <PlusIcon className="w-4 h-4" />
          Add Knowledge
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-6 z-10 flex gap-3">
        <div className="flex-1 relative">
          <MagnifyingGlassIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-jarvis-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder="Search your knowledge semantically..."
            className="w-full bg-jarvis-panel border border-jarvis-border rounded-full py-3 pl-12 pr-4 text-jarvis-text placeholder:text-jarvis-muted text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary transition-shadow"
          />
        </div>
        <button
          onClick={handleSearch}
          className="px-5 py-2.5 rounded-full bg-jarvis-accent-primary text-white text-sm font-medium hover:bg-jarvis-accent-hover transition-all"
        >
          Search
        </button>
      </div>

      {/* Add Form */}
      {showForm && (
        <div className="mb-6 p-5 rounded-[8px] bg-jarvis-surface border border-jarvis-border shadow-sm z-10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-jarvis-text font-medium flex items-center gap-2">
              <LightBulbIcon className="w-5 h-5 text-yellow-400" />
              Add Knowledge
            </h3>
            <button
              onClick={() => setShowForm(false)}
              className="text-jarvis-muted hover:text-jarvis-text"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>
          <p className="text-jarvis-muted text-xs mb-3">
            Knowledge you add here is embedded into vector memory and becomes available to the agent for reasoning.
          </p>
          <textarea
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            placeholder="Enter knowledge, notes, goals, or important information..."
            rows={4}
            className="w-full bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-3 text-jarvis-text placeholder:text-jarvis-muted text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary resize-none"
          />
          <div className="flex items-center gap-3 mt-3">
            <select
              value={newTopic}
              onChange={(e) => setNewTopic(e.target.value)}
              className="bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-2.5 text-jarvis-text text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary"
            >
              <option value="general">General</option>
              <option value="personal_info">Personal Info</option>
              <option value="goal">Goal</option>
              <option value="preference">Preference</option>
              <option value="learning">Learning</option>
            </select>
            <button
              onClick={handleAdd}
              disabled={!newContent.trim() || saving}
              className="px-6 py-2.5 rounded-[4px] bg-jarvis-accent-primary text-white text-sm font-medium hover:bg-jarvis-accent-hover disabled:opacity-40 transition-all"
            >
              {saving ? "Saving..." : "Store in Memory"}
            </button>
          </div>
        </div>
      )}

      {/* Knowledge List */}
      <div className="flex-1 overflow-y-auto z-10 pb-8">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="text-jarvis-muted text-sm">Loading knowledge...</div>
          </div>
        ) : entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-jarvis-muted">
            <DocumentTextIcon className="w-12 h-12 mb-3 opacity-30" />
            <p className="text-sm">No knowledge entries found. Add some above.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {entries.map((entry, i) => (
              <div
                key={i}
                className="p-5 rounded-[8px] bg-jarvis-surface border border-transparent hover:border-jarvis-border shadow-sm transition-all duration-200"
              >
                <div className="flex items-start justify-between gap-4">
                  <p className="text-[14px] text-jarvis-text leading-relaxed flex-1">
                    {entry.content}
                  </p>
                  {entry.score !== undefined && (
                    <span className="text-[10px] text-jarvis-muted shrink-0">
                      {(entry.score * 100).toFixed(0)}% match
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 mt-3">
                  {entry.topic && (
                    <span
                      className={`text-[10px] px-2.5 py-1 rounded-full font-medium uppercase tracking-[0.1em] ${
                        topicColors[entry.topic] || topicColors.general
                      }`}
                    >
                      {entry.topic}
                    </span>
                  )}
                  {entry.source_filename && (
                    <span className="text-[10px] text-jarvis-muted">
                      Source: {entry.source_filename}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
