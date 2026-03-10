import React from "react";
import { CheckCircleIcon, CalendarDaysIcon, PlusIcon } from "@heroicons/react/24/outline";

export default function TasksWidget() {
    const tasks = [
        { title: "Review Q3 Report", time: "10:00 AM", category: "Work", status: "completed", offsetClass: "translate-x-[-30px] translate-y-2" },
        { title: "Update UI Components", time: "2:00 PM", category: "Project", status: "pending", offsetClass: "translate-x-[40px] translate-y-0" },
        { title: "Client Sync", time: "4:00 PM", category: "Meeting", status: "pending", offsetClass: "translate-x-[-15px] translate-y-4" },
        { title: "Buy Groceries", time: "6:00 PM", category: "Personal", status: "pending", offsetClass: "translate-x-[25px] translate-y-1" },
    ];

    return (
        <div className="flex-1 flex flex-col h-full bg-transparent p-6 md:p-10 lg:p-14 overflow-hidden relative">
            <div className="flex items-center justify-between mb-16 z-10 group/header">
                <div>
                    <h2 className="text-3xl font-light text-jarvis-text tracking-wide drop-shadow-sm transition-all duration-500 group-hover/header:translate-x-2">Tasks Cloud</h2>
                    <p className="text-jarvis-muted mt-2 text-[14px] font-light tracking-wide transition-all duration-500 group-hover/header:translate-x-2">4 tasks remaining today</p>
                </div>
                <button className="flex items-center gap-2 px-6 py-3 rounded-full bg-jarvis-glass-bg border border-jarvis-accent-cyan text-jarvis-accent-cyan text-[14px] font-medium transition-all duration-500 shadow-halo-cyan hover:bg-jarvis-accent-cyan hover:text-white hover:shadow-[0_0_30px_rgba(0,240,255,0.6)] group hover:-translate-y-1">
                    <PlusIcon className="w-5 h-5 group-hover:rotate-90 transition-transform duration-500" />
                    New Task
                </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-8 pr-4 z-10 pb-32 flex flex-col items-center justify-start ml-4">
                {tasks.map((task, i) => (
                    <div 
                        key={i} 
                        className={`w-full max-w-[450px] flex items-center gap-5 p-5 rounded-[28px] bg-jarvis-glass-bg backdrop-blur-2xl border border-jarvis-glass-border shadow-halo hover:shadow-halo-cyan transition-all duration-700 cursor-pointer group hover:-translate-y-3 hover:bg-jarvis-glass-border animate-float ${task.offsetClass}`}
                        style={{ animationDelay: `${i * 1.5}s` }}
                    >
                        <CheckCircleIcon className={`w-8 h-8 transition-colors duration-500 ${task.status === "completed" ? "text-jarvis-accent-cyan shadow-[0_0_15px_rgba(0,240,255,0.4)] rounded-full" : "text-jarvis-muted/40 group-hover:text-jarvis-accent-cyan"}`} />
                        <div className="flex-1">
                            <h3 className={`text-[16px] font-medium tracking-wide transition-colors duration-500 ${task.status === "completed" ? "text-jarvis-muted line-through" : "text-jarvis-text group-hover:text-white"}`}>
                                {task.title}
                            </h3>
                            <div className="flex items-center gap-4 mt-2.5">
                                <span className="flex items-center gap-1.5 text-[12px] font-light text-jarvis-muted tracking-wide">
                                    <CalendarDaysIcon className="w-4 h-4" />
                                    {task.time}
                                </span>
                                <span className="text-[10px] px-3 py-1.5 rounded-full bg-jarvis-glass-border text-jarvis-muted font-medium uppercase tracking-[0.15em] border border-jarvis-glass-border group-hover:text-jarvis-text transition-colors duration-500">
                                    {task.category}
                                </span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
