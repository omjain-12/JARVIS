import React, { useCallback, useEffect, useState } from "react";
import {
  CheckCircleIcon,
  CalendarDaysIcon,
  PlusIcon,
  ClockIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import { getTasks, createTask, getReminders, createReminder, updateTaskStatus } from "@/services/api";
import type { TaskItem, ReminderItem } from "@/types";

export default function TasksDashboard() {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [reminders, setReminders] = useState<ReminderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [showReminderForm, setShowReminderForm] = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDesc, setTaskDesc] = useState("");
  const [taskPriority, setTaskPriority] = useState(0);
  const [taskDueDate, setTaskDueDate] = useState("");
  const [reminderTitle, setReminderTitle] = useState("");
  const [reminderMessage, setReminderMessage] = useState("");
  const [reminderAt, setReminderAt] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [t, r] = await Promise.all([getTasks(), getReminders()]);
      setTasks(t);
      setReminders(r);
    } catch {
      // Data unavailable
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreateTask = async () => {
    if (!taskTitle.trim()) return;
    try {
      await createTask(taskTitle, taskDesc, taskPriority, taskDueDate);
      setTaskTitle("");
      setTaskDesc("");
      setTaskPriority(0);
      setTaskDueDate("");
      setShowTaskForm(false);
      loadData();
    } catch {
      // Failed to create
    }
  };

  const handleCreateReminder = async () => {
    if (!reminderTitle.trim() || !reminderAt) return;
    try {
      await createReminder(reminderTitle, reminderMessage, reminderAt);
      setReminderTitle("");
      setReminderMessage("");
      setReminderAt("");
      setShowReminderForm(false);
      loadData();
    } catch {
      // Failed to create
    }
  };

  const handleToggleTask = async (taskId: string, currentStatus: string) => {
    try {
      const newStatus = currentStatus === "completed" ? "pending" : "completed";
      await updateTaskStatus(taskId, newStatus);
      loadData();
    } catch {
      // Failed to update
    }
  };

  const priorityLabel = (p: number) =>
    p === 2 ? "High" : p === 1 ? "Medium" : "Low";

  const priorityColor = (p: number) =>
    p === 2
      ? "text-[#ff6b6b] bg-[rgba(255,90,90,0.12)] border border-[#ff6b6b]/20 shadow-[0_0_12px_rgba(255,90,90,0.4)]"
      : p === 1
        ? "text-yellow-400 bg-yellow-400/10 border-yellow-400/20 shadow-[0_0_12px_rgba(250,204,21,0.4)]"
        : "text-jarvis-muted bg-white/5 border-white/5";

  return (
    <div className="flex-1 flex flex-col h-full bg-transparent p-6 md:p-10 lg:p-14 overflow-hidden relative">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 z-10">
        <div>
          <h2 className="text-3xl font-light text-jarvis-text tracking-wide drop-shadow-sm">
            Tasks & Reminders
          </h2>
          <p className="text-jarvis-muted mt-2 text-[14px] font-light tracking-wide">
            {tasks.length} tasks · {reminders.length} reminders
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowReminderForm(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-[4px] bg-transparent border border-jarvis-border text-jarvis-text-secondary text-[13px] font-medium transition-all duration-150 hover:bg-jarvis-surface/50 hover:text-jarvis-text"
          >
            <ClockIcon className="w-4 h-4" />
            Reminder
          </button>
          <button
            onClick={() => setShowTaskForm(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-[4px] bg-jarvis-accent-primary text-white text-[13px] font-medium transition-all duration-150 hover:brightness-110"
          >
            <PlusIcon className="w-4 h-4" />
            New Task
          </button>
        </div>
      </div>

      {/* Inline Forms */}
      {showTaskForm && (
        <div className="mb-6 p-6 rounded-[12px] bg-jarvis-surface border border-jarvis-border shadow-card hover z-10 transition-all duration-200">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-jarvis-text font-medium text-[15px]">Create Task</h3>
            <button onClick={() => setShowTaskForm(false)} className="text-jarvis-muted hover:text-jarvis-text transition-colors">
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
              placeholder="Task title"
              className="bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-2.5 text-jarvis-text placeholder:text-jarvis-muted text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary"
            />
            <input
              value={taskDesc}
              onChange={(e) => setTaskDesc(e.target.value)}
              placeholder="Description (optional)"
              className="bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-2.5 text-jarvis-text placeholder:text-jarvis-muted text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary"
            />
            <select
              value={taskPriority}
              onChange={(e) => setTaskPriority(Number(e.target.value))}
              className="bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-2.5 text-jarvis-text text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary"
            >
              <option value={0}>Low Priority</option>
              <option value={1}>Medium Priority</option>
              <option value={2}>High Priority</option>
            </select>
            <input
              type="datetime-local"
              value={taskDueDate}
              onChange={(e) => setTaskDueDate(e.target.value)}
              className="bg-jarvis-surface border border-jarvis-border rounded-[10px] px-3.5 py-2.5 text-jarvis-text text-[14px] focus:outline-none focus:border-jarvis-accent-primary focus:shadow-focus-ring"
            />
          </div>
          <button
            onClick={handleCreateTask}
            disabled={!taskTitle.trim()}
            className="mt-4 px-4 py-2.5 rounded-[4px] bg-jarvis-accent-primary text-white text-[14px] font-medium hover:brightness-110 disabled:opacity-40 transition-all duration-150"
          >
            Create Task
          </button>
        </div>
      )}

      {showReminderForm && (
        <div className="mb-6 p-6 rounded-[12px] bg-jarvis-surface border border-jarvis-border shadow-card z-10 transition-all duration-200">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-jarvis-text font-medium text-[15px]">Create Reminder</h3>
            <button onClick={() => setShowReminderForm(false)} className="text-jarvis-muted hover:text-jarvis-text transition-colors">
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              value={reminderTitle}
              onChange={(e) => setReminderTitle(e.target.value)}
              placeholder="Reminder title"
              className="bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-2.5 text-jarvis-text placeholder:text-jarvis-muted text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary"
            />
            <input
              value={reminderMessage}
              onChange={(e) => setReminderMessage(e.target.value)}
              placeholder="Message (optional)"
              className="bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-2.5 text-jarvis-text placeholder:text-jarvis-muted text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary"
            />
            <input
              type="datetime-local"
              value={reminderAt}
              onChange={(e) => setReminderAt(e.target.value)}
              className="bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-2.5 text-jarvis-text text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary md:col-span-2"
            />
          </div>
          <button
            onClick={handleCreateReminder}
            disabled={!reminderTitle.trim() || !reminderAt}
            className="mt-4 px-6 py-2.5 rounded-[4px] bg-jarvis-accent-primary text-white text-sm font-medium hover:opacity-90 disabled:opacity-40 transition-all"
          >
            Create Reminder
          </button>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto z-10 pb-8 space-y-8">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="text-jarvis-muted text-sm">Loading...</div>
          </div>
        ) : (
          <>
            {/* Tasks Section */}
            <div>
              <h3 className="text-jarvis-text/80 text-sm font-medium uppercase tracking-[0.15em] mb-4">
                Tasks
              </h3>
              {tasks.length === 0 ? (
                <div className="text-jarvis-muted text-sm p-4">No tasks yet. Create one above.</div>
              ) : (
                <div className="space-y-3">
                  {tasks.map((task) => (
                    <div
                      key={task.id}
                      className="flex items-center gap-4 p-4 rounded-[12px] bg-jarvis-surface shadow-[0_2px_8px_rgba(0,0,0,0.04)] dark:shadow-[0_2px_8px_rgba(0,0,0,0.15)] transition-all duration-150 cursor-pointer group hover:-translate-y-[2px] hover:shadow-[0_6px_20px_rgba(0,0,0,0.08)] dark:hover:shadow-[0_6px_20px_rgba(0,0,0,0.3)]"
                    >
                      <CheckCircleIcon
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleTask(task.id, task.status);
                        }}
                        className={`w-6 h-6 transition-colors duration-300 cursor-pointer flex-shrink-0 ${
                          task.status === "completed"
                            ? "text-jarvis-success shadow-[0_0_10px_rgba(34,197,94,0.3)] rounded-full"
                            : "text-jarvis-muted/40 hover:text-jarvis-success group-hover:text-jarvis-muted"
                        }`}
                      />
                      <div className="flex-1 min-w-0">
                        <h4
                          className={`text-[15px] font-medium tracking-wide transition-colors ${
                            task.status === "completed"
                              ? "text-jarvis-muted line-through"
                              : "text-jarvis-text"
                          }`}
                        >
                          {task.title}
                        </h4>
                        {task.description && (
                          <p className="text-jarvis-muted text-xs mt-1 truncate">
                            {task.description}
                          </p>
                        )}
                        <div className="flex items-center gap-3 mt-2">
                          {task.due_date && (
                            <span className="flex items-center gap-1 text-[11px] text-jarvis-muted">
                              <CalendarDaysIcon className="w-3.5 h-3.5" />
                              {new Date(task.due_date).toLocaleDateString()}
                            </span>
                          )}
                          <span
                            className={`text-[10px] px-2.5 py-1 rounded-full border font-medium uppercase tracking-[0.1em] ${priorityColor(
                              task.priority,
                            )}`}
                          >
                            {priorityLabel(task.priority)}
                          </span>
                          <span className="text-[10px] px-2.5 py-1 rounded-full bg-white/5 text-jarvis-muted border border-white/5 uppercase tracking-[0.1em]">
                            {task.status}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Reminders Section */}
            <div>
              <h3 className="text-jarvis-text/80 text-sm font-medium uppercase tracking-[0.15em] mb-4">
                Reminders
              </h3>
              {reminders.length === 0 ? (
                <div className="text-jarvis-muted text-sm p-4">No reminders yet.</div>
              ) : (
                <div className="space-y-3">
                  {reminders.map((r) => (
                    <div
                      key={r.id}
                      className="flex items-center gap-4 p-4 rounded-[12px] bg-jarvis-surface shadow-[0_2px_8px_rgba(0,0,0,0.04)] dark:shadow-[0_2px_8px_rgba(0,0,0,0.15)] transition-all duration-150 group hover:-translate-y-[2px] hover:shadow-[0_6px_20px_rgba(0,0,0,0.08)] dark:hover:shadow-[0_6px_20px_rgba(0,0,0,0.3)]"
                    >
                      <ClockIcon className="w-6 h-6 text-jarvis-accent-secondary flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <h4 className="text-[15px] font-medium text-jarvis-text">
                          {r.title}
                        </h4>
                        {r.message && (
                          <p className="text-jarvis-muted text-xs mt-1">{r.message}</p>
                        )}
                        <span className="text-[11px] text-jarvis-muted mt-1 block">
                          {new Date(r.remind_at).toLocaleString()}
                        </span>
                      </div>
                      {r.is_sent && (
                        <span className="text-[10px] px-2 py-1 rounded-full bg-green-400/10 text-green-400 border border-green-400/20">
                          Sent
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
