import React, { useMemo, useState, useEffect } from "react";
import { ChevronLeftIcon, ChevronRightIcon } from "@heroicons/react/24/outline";
import { getTasks, getReminders } from "@/services/api";
import type { TaskItem, ReminderItem } from "@/types";

export default function CalendarWidget() {
    const hours = Array.from({ length: 12 }, (_, i) => i + 8); // 8 AM to 7 PM
    const [weekOffset, setWeekOffset] = useState(0);
    const [tasks, setTasks] = useState<TaskItem[]>([]);
    const [reminders, setReminders] = useState<ReminderItem[]>([]);

    useEffect(() => {
        getTasks("demo_user").then(setTasks).catch(() => {});
        getReminders("demo_user").then(setReminders).catch(() => {});
    }, []);

    const { weekDays, monthLabel, weekNumber } = useMemo(() => {
        const now = new Date();
        // Move to Monday of the current week then apply offset
        const monday = new Date(now);
        const dayOfWeek = now.getDay();
        const diff = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
        monday.setDate(now.getDate() + diff + weekOffset * 7);

        const days = Array.from({ length: 7 }, (_, i) => {
            const d = new Date(monday);
            d.setDate(monday.getDate() + i);
            return d;
        });

        const fmt = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" });
        const label = fmt.format(days[0]);

        // Week number (ISO)
        const jan1 = new Date(days[3].getFullYear(), 0, 1);
        const wn = Math.ceil(((days[3].getTime() - jan1.getTime()) / 86400000 + jan1.getDay() + 1) / 7);

        return { weekDays: days, monthLabel: label, weekNumber: wn };
    }, [weekOffset]);

    const todayStr = new Date().toDateString();
    const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

    return (
        <div className="flex-1 flex flex-col h-full bg-jarvis-bg overflow-hidden p-6 md:p-12 relative z-0">
            <div className="absolute top-0 inset-x-0 h-40 bg-gradient-to-b from-jarvis-alert-amber/10 to-transparent pointer-events-none" />

            {/* Header */}
            <div className="flex items-center justify-between mb-8 z-10">
                <div>
                    <h2 className="text-3xl font-semibold text-jarvis-text tracking-tight drop-shadow-sm">{monthLabel}</h2>
                    <p className="text-jarvis-muted mt-1.5 text-[14px]">Week {weekNumber}</p>
                </div>
                <div className="flex gap-2">
                    <button onClick={() => setWeekOffset((o) => o - 1)} className="p-2.5 rounded-full bg-jarvis-glass-bg border border-jarvis-glass-border hover:bg-jarvis-surface transition-colors">
                        <ChevronLeftIcon className="w-5 h-5 text-jarvis-muted" />
                    </button>
                    <button onClick={() => setWeekOffset(0)} className="px-5 py-2.5 rounded-full bg-jarvis-surface backdrop-blur-xl border border-jarvis-glass-border text-sm font-medium hover:bg-jarvis-panel transition-colors text-jarvis-text shadow-sm">
                        Today
                    </button>
                    <button onClick={() => setWeekOffset((o) => o + 1)} className="p-2.5 rounded-full bg-jarvis-glass-bg border border-jarvis-glass-border hover:bg-jarvis-surface transition-colors">
                        <ChevronRightIcon className="w-5 h-5 text-jarvis-muted" />
                    </button>
                </div>
            </div>

            {/* Calendar Grid */}
            <div className="flex-1 overflow-y-auto bg-jarvis-surface border border-jarvis-border shadow-panel rounded-[16px] p-6 flex flex-col relative z-10 transition-all duration-200">
                {/* Days Header */}
                <div className="grid grid-cols-8 gap-4 mb-4 border-b border-black/5 dark:border-[#222222] pb-4">
                    <div className="text-right pr-4 pt-1">
                        <span className="text-[11px] text-jarvis-muted font-semibold uppercase tracking-widest">Time</span>
                    </div>
                    {weekDays.map((d, i) => {
                        const isToday = d.toDateString() === todayStr;
                        return (
                            <div key={i} className="text-center font-medium">
                                <span className={`text-[14px] ${isToday ? "text-jarvis-accent-primary font-semibold" : "text-jarvis-muted"}`}>
                                    {dayNames[i]} {d.getDate()}
                                </span>
                            </div>
                        );
                    })}
                </div>

                {/* Timeline */}
                <div className="flex-1 overflow-y-auto relative min-h-0 pr-2">
                    {hours.map((hour) => (
                        <div key={hour} className="grid grid-cols-8 gap-4 min-h-[48px] border-b border-black/5 dark:border-[#222222] group">
                            <div className="text-right pr-4 relative">
                                <span className="text-[11px] font-medium text-jarvis-muted/70 relative -top-2.5 bg-jarvis-surface px-2 py-0.5 rounded border border-black/5 dark:border-[#222222]">
                                    {hour > 12 ? `${hour - 12} PM` : hour === 12 ? "12 PM" : `${hour} AM`}
                                </span>
                            </div>
                            {weekDays.map((d, col) => {
                                const isToday = d.toDateString() === todayStr;
                                const cellDateStart = new Date(d);
                                cellDateStart.setHours(hour, 0, 0, 0);
                                const cellDateEnd = new Date(d);
                                cellDateEnd.setHours(hour + 1, 0, 0, 0);

                                const cellTasks = tasks.filter(t => {
                                    if (!t.due_date) return false;
                                    const tDate = new Date(t.due_date);
                                    return tDate >= cellDateStart && tDate < cellDateEnd;
                                });
                                const cellReminders = reminders.filter(r => {
                                    if (!r.remind_at) return false;
                                    const rDate = new Date(r.remind_at);
                                    return rDate >= cellDateStart && rDate < cellDateEnd;
                                });

                                return (
                                    <div key={col} className={`col-span-1 border-l border-black/5 dark:border-[#222222] h-full transition-colors relative p-1.5 space-y-1.5 overflow-hidden ${isToday ? "bg-black/5 dark:bg-[rgba(255,255,255,0.02)] group-hover:bg-black/10 dark:group-hover:bg-[rgba(255,255,255,0.04)]" : "group-hover:bg-black/5 dark:group-hover:bg-[rgba(255,255,255,0.02)]"}`}>
                                        {cellTasks.map(t => (
                                            <div key={t.id} className="text-[10px] sm:text-[11px] bg-[#0078D4] text-white rounded-[4px] px-2 py-1 truncate shadow-sm cursor-pointer hover:-translate-y-[1px] hover:shadow-card-hover transition-all" title={t.title}>
                                                {t.title}
                                            </div>
                                        ))}
                                        {cellReminders.map(r => (
                                            <div key={r.id} className="text-[10px] sm:text-[11px] bg-[#005A9E] text-white rounded-[4px] px-2 py-1 truncate shadow-sm cursor-pointer hover:-translate-y-[1px] hover:shadow-card-hover transition-all" title={r.title}>
                                                {r.title}
                                            </div>
                                        ))}
                                    </div>
                                );
                            })}
                        </div>
                    ))}
                </div>

                {/* Empty‑state hint when no tasks */}
                {tasks.length === 0 && (
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <p className="text-jarvis-muted text-sm">Ask Jarvis to schedule events!</p>
                    </div>
                )}
            </div>
        </div>
    );
}
