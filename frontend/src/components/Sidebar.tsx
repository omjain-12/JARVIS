import React, { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import {
    HomeIcon,
    CalendarIcon,
    ChatBubbleLeftRightIcon,
    DocumentTextIcon,
    CheckCircleIcon,
    SunIcon,
    MoonIcon,
    UserGroupIcon,
    LightBulbIcon,
    CpuChipIcon,
} from "@heroicons/react/24/outline";

interface SidebarProps {
    activeTab: string;
    onTabChange: (tab: string) => void;
}

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
    const { theme, setTheme } = useTheme();
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    const navItems = [
        { id: "home", label: "Home", icon: HomeIcon },
        { id: "calendar", label: "Calendar", icon: CalendarIcon },
        { id: "tasks", label: "Tasks", icon: CheckCircleIcon },
        { id: "contacts", label: "Contacts", icon: UserGroupIcon },
        { id: "knowledge", label: "Knowledge", icon: LightBulbIcon },
        { id: "memory", label: "Memory", icon: CpuChipIcon },
        { id: "communications", label: "Comms", icon: ChatBubbleLeftRightIcon },
    ];

    return (
        <div className="w-[240px] h-full bg-jarvis-bg flex flex-col justify-between p-5 flex-shrink-0 relative z-20 transition-all duration-200">
            {/* Navigation Links */}
            <nav className="flex-1 space-y-3 mt-12 md:mt-15">
                {navItems.map((item) => {
                    const isActive = activeTab === item.id;
                    const Icon = item.icon;
                    return (
                        <button
                            key={item.id}
                            onClick={() => onTabChange(item.id)}
                            className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-[8px] transition-all duration-150 text-[14px] font-medium relative ${isActive
                                ? "bg-jarvis-surface text-jarvis-text shadow-[0_2px_8px_rgba(0,0,0,0.2)] border border-jarvis-border/50"
                                : "text-jarvis-muted hover:bg-jarvis-surface/50 hover:text-jarvis-text"
                                }`}
                        >
                            {isActive && (
                                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 bg-copilot-gradient rounded-r-md" />
                            )}
                            <Icon
                                className={`w-5 h-5 transition-colors duration-500 ${isActive ? "text-jarvis-accent-primary" : "text-jarvis-muted"
                                    }`}
                            />
                            {item.label}
                        </button>
                    );
                })}
            </nav>

            <div className="mt-auto flex flex-col gap-2">
                {/* Theme Toggle Button */}
                {mounted && (
                    <button
                        onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                        className="flex items-center gap-3 px-4 py-3 w-full rounded-[8px] text-jarvis-muted hover:bg-jarvis-surface/50 hover:text-jarvis-text transition-all duration-150 text-[14px] font-medium"
                    >
                        {theme === 'dark' ? (
                            <SunIcon className="w-5 h-5 text-jarvis-accent-primary" />
                        ) : (
                            <MoonIcon className="w-5 h-5 text-jarvis-accent-primary" />
                        )}
                        <span>{theme === 'dark' ? 'Light Mode' : 'The Void'}</span>
                    </button>
                )}

                {/* Bottom Profile Section */}
                <div className="px-3 py-3 border-t border-jarvis-border flex items-center gap-3 cursor-pointer hover:bg-jarvis-surface/50 rounded-[8px] transition-all duration-150 group mt-2">
                    <div className="w-10 h-10 rounded-full bg-jarvis-panel flex items-center justify-center border border-jarvis-border shadow-sm overflow-hidden ring-2 ring-transparent group-hover:ring-jarvis-accent-primary/30 transition-all">
                        <img src="https://ui-avatars.com/api/?name=Om+Jain&background=0078D4&color=fff&bold=true&font-size=0.4" alt="OJ" className="w-full h-full object-cover" />
                    </div>
                    <div className="flex flex-col text-left">
                        <span className="text-[13px] font-medium text-jarvis-text/90 group-hover:text-jarvis-text transition-colors">Om Jain</span>
                        <span className="text-[11px] text-jarvis-muted font-light tracking-wide">Workspace Admin</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
