import React, { useEffect, useState } from "react";
import { EnvelopeIcon, ChatBubbleOvalLeftEllipsisIcon, PhoneIcon } from "@heroicons/react/24/outline";
import { getContacts } from "@/services/api";
import type { ContactItem } from "@/types";

const channelIcon = (rel: string) => {
    const low = (rel || "").toLowerCase();
    if (low.includes("work") || low.includes("colleague")) return EnvelopeIcon;
    if (low.includes("family") || low.includes("friend")) return ChatBubbleOvalLeftEllipsisIcon;
    return PhoneIcon;
};

const channelLabel = (rel: string) => {
    const low = (rel || "").toLowerCase();
    if (low.includes("work") || low.includes("colleague")) return "email";
    if (low.includes("family") || low.includes("friend")) return "sms";
    return "phone";
};

export default function CommsWidget() {
    const [contacts, setContacts] = useState<ContactItem[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        getContacts("demo_user")
            .then(setContacts)
            .catch(() => {})
            .finally(() => setLoading(false));
    }, []);

    return (
        <div className="flex-1 flex flex-col h-full bg-jarvis-bg p-6 md:p-10 lg:p-14 overflow-hidden relative">
            <div className="absolute top-0 inset-x-0 h-40 bg-gradient-to-b from-green-500/5 to-transparent pointer-events-none" />

            <div className="flex items-center justify-between mb-8 z-10">
                <div>
                    <h2 className="text-3xl font-semibold text-jarvis-text tracking-tight drop-shadow-sm">Communications</h2>
                    <p className="text-jarvis-muted mt-1.5 text-sm">Recent contacts and messaging channels</p>
                </div>
                <button className="p-2.5 rounded-[4px] bg-jarvis-surface text-jarvis-muted hover:bg-jarvis-panel hover:text-jarvis-text transition-colors border border-transparent hover:border-jarvis-border">
                    <EnvelopeIcon className="w-5 h-5" />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-2 z-10">
                {loading && (
                    <div className="flex items-center gap-3 p-6 text-jarvis-muted">
                        <div className="w-4 h-4 border-2 border-jarvis-accent-primary border-t-transparent rounded-full animate-spin" />
                        Loading…
                    </div>
                )}

                {!loading && contacts.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-20 text-jarvis-muted">
                        <ChatBubbleOvalLeftEllipsisIcon className="w-12 h-12 mb-4 opacity-30" />
                        <p className="text-sm">No contacts yet. Ask Jarvis to save a contact!</p>
                    </div>
                )}

                {contacts.map((c) => {
                    const Icon = channelIcon(c.relationship || "");
                    const channel = channelLabel(c.relationship || "");
                    const detail = channel === "email" && c.email ? c.email : c.phone || c.notes || "";
                    return (
                        <div key={c.id} className="flex items-start gap-4 p-4 rounded-[8px] bg-jarvis-surface border border-transparent shadow-sm hover:border-jarvis-border hover:shadow-md transition-all cursor-pointer group">
                            <div className="w-12 h-12 rounded-full flex items-center justify-center border bg-jarvis-panel border-transparent text-jarvis-muted group-hover:text-jarvis-accent-primary group-hover:border-jarvis-accent-primary/30 transition-colors">
                                <Icon className="w-6 h-6" />
                            </div>
                            <div className="flex-1 mt-1 min-w-0">
                                <div className="flex justify-between items-start">
                                    <h3 className="text-[15px] font-semibold tracking-tight text-jarvis-text group-hover:text-jarvis-text transition-colors truncate">{c.name}</h3>
                                    {c.relationship && (
                                        <span className="text-[11px] text-jarvis-muted ml-2 flex-shrink-0">{c.relationship}</span>
                                    )}
                                </div>
                                {detail && (
                                    <p className="text-[14px] mt-1 text-jarvis-muted truncate">{detail}</p>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
