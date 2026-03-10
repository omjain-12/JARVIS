import React, { useEffect, useState } from "react";
import { getTasks, getReminders, getHealth } from "@/services/api";
import type { TaskItem, ReminderItem, HealthStatus } from "@/types";

export default function RightPanel() {
    const [tasks, setTasks] = useState<TaskItem[]>([]);
    const [reminders, setReminders] = useState<ReminderItem[]>([]);
    const [health, setHealth] = useState<HealthStatus | null>(null);

    useEffect(() => {
        getTasks("demo_user", "pending").then(setTasks).catch(() => {});
        getReminders("demo_user").then(setReminders).catch(() => {});
        getHealth().then(setHealth).catch(() => {});
    }, []);

    const pendingReminders = reminders.filter((r) => !r.is_sent);
    const today = new Date();
    const dateLabel = today.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });

    const priorityColors = [
        "bg-jarvis-muted shadow-none",
        "bg-[#F59E0B] shadow-[0_0_8px_rgba(245,158,11,0.8)]",
        "bg-[#ff6b6b] shadow-[0_0_8px_rgba(255,107,107,0.8)]",
    ];

    return (
        <div className="w-[300px] h-full flex flex-col flex-shrink-0 space-y-6 relative z-20 transition-all duration-200 bg-transparent py-6 pr-4">
            <div className="flex items-center justify-between mb-0 px-2">
                <h2 className="text-[13px] font-bold text-black dark:text-white uppercase tracking-[0.1em]">
                    {dateLabel}
                </h2>
            </div>

            {/* Upcoming Tasks */}
            <div className="bg-white dark:bg-[#161616] border border-black/5 dark:border-[#2D2D2D] rounded-[8px] p-4 relative group transition-all duration-150">
                <h3 className="text-gray-900 dark:text-white font-semibold mb-3 text-[14px]">Tasks</h3>
                <div className="space-y-4">
                    {tasks.length === 0 ? (
                        <p className="text-[13px] text-jarvis-muted">No pending tasks</p>
                    ) : (
                        tasks.slice(0, 4).map((task) => (
                            <div key={task.id} className="flex gap-4 relative items-start">
                                <div className={`w-1.5 h-1.5 mt-1.5 rounded-full flex-shrink-0 ${priorityColors[task.priority] || priorityColors[0]}`} />
                                <div className="min-w-0">
                                    <p className="text-[14px] font-medium text-jarvis-text leading-tight truncate">{task.title}</p>
                                    {task.due_date && (
                                        <p className="text-[11px] text-jarvis-muted mt-1 font-light">{task.due_date}</p>
                                    )}
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Active Reminders */}
            <div className="bg-white dark:bg-[#161616] border border-black/5 dark:border-[#2D2D2D] rounded-[8px] p-4 flex flex-col flex-1 overflow-y-auto group transition-all duration-150">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-jarvis-text font-medium text-[14px] tracking-wide">Reminders</h3>
                    {pendingReminders.length > 0 && (
                        <span className="bg-jarvis-alert-pink/10 text-jarvis-alert-pink text-[10px] font-bold px-2 py-0.5 rounded-full border border-jarvis-alert-pink/20 shadow-[0_0_10px_rgba(255,0,127,0.2)]">
                            {pendingReminders.length}
                        </span>
                    )}
                </div>
                <ul className="space-y-2">
                    {pendingReminders.length === 0 ? (
                        <li className="text-[13px] text-jarvis-muted">No upcoming reminders</li>
                    ) : (
                        pendingReminders.slice(0, 5).map((rem) => (
                            <li key={rem.id} className="flex items-start gap-4 p-3 hover:bg-[rgba(255,255,255,0.03)] dark:hover:bg-[rgba(255,255,255,0.03)] hover:bg-[rgba(0,0,0,0.02)] rounded-[8px] transition-all duration-150 cursor-pointer group/item border border-transparent">
                                <div className="w-4 h-4 mt-0.5 rounded-full border border-jarvis-muted/40 group-hover/item:border-jarvis-accent-cyan group-hover/item:shadow-[0_0_8px_rgba(0,240,255,0.4)] flex items-center justify-center transition-all flex-shrink-0" />
                                <div className="min-w-0">
                                    <span className="text-[13.5px] font-medium text-jarvis-muted group-hover/item:text-jarvis-text transition-colors leading-relaxed block truncate">
                                        {rem.title}
                                    </span>
                                    {rem.remind_at && (
                                        <span className="text-[11px] text-jarvis-muted/60 mt-0.5 block">
                                            {new Date(rem.remind_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
                                        </span>
                                    )}
                                </div>
                            </li>
                        ))
                    )}
                </ul>
            </div>

            {/* Health / Status Widget */}
            <div className="h-[52px] rounded-[8px] bg-white dark:bg-[#161616] border border-black/5 dark:border-[#2D2D2D] flex items-center justify-between px-4 mt-auto">
                <div className="flex items-center gap-3">
                    <div className="relative flex h-2 w-2">
                        <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${health ? "bg-jarvis-success" : "bg-jarvis-warning"} opacity-75`}></span>
                        <span className={`relative inline-flex rounded-full h-2 w-2 ${health ? "bg-jarvis-success shadow-[0_0_8px_rgba(34,197,94,0.6)]" : "bg-jarvis-warning shadow-[0_0_8px_rgba(245,158,11,0.6)]"}`}></span>
                    </div>
                    <span className="text-[13px] font-medium tracking-wide text-jarvis-muted">
                        {health ? "System Online" : "Connecting…"}
                    </span>
                </div>
            </div>
        </div>
    );
}
