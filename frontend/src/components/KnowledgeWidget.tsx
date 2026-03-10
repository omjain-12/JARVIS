import React from "react";
import { DocumentTextIcon, FolderIcon, MagnifyingGlassIcon } from "@heroicons/react/24/outline";

export default function KnowledgeWidget() {
    const documents = [
        { title: "Project Alpha Spec", type: "pdf", size: "2.4 MB", date: "Today" },
        { title: "Q3 Financials", type: "sheet", size: "1.1 MB", date: "Yesterday" },
        { title: "Meeting Notes - Sync", type: "doc", size: "45 KB", date: "Sep 12" },
        { title: "Brand Guidelines", type: "pdf", size: "5.7 MB", date: "Sep 10" },
    ];

    return (
        <div className="flex-1 flex flex-col h-full bg-jarvis-bg p-6 md:p-10 lg:p-14 overflow-hidden relative">
            <div className="absolute top-0 inset-x-0 h-40 bg-gradient-to-b from-purple-500/5 to-transparent pointer-events-none" />

            <div className="flex items-center justify-between mb-8 z-10">
                <div>
                    <h2 className="text-3xl font-semibold text-white tracking-tight drop-shadow-sm">Knowledge</h2>
                    <p className="text-white/60 mt-1.5 text-sm">Your indexed documents and context</p>
                </div>
            </div>

            <div className="relative mb-8 z-10">
                <MagnifyingGlassIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
                <input
                    type="text"
                    placeholder="Search your brain..."
                    className="w-full bg-[#1C1C1E]/80 backdrop-blur-xl border border-white/10 rounded-full py-3.5 pl-12 pr-4 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-[#0A84FF]/50 transition-shadow shadow-md"
                />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 overflow-y-auto pr-2 z-10">
                {documents.map((doc, i) => (
                    <div key={i} className="flex items-start gap-4 p-5 rounded-3xl bg-[#1C1C1E]/60 backdrop-blur-2xl border border-white/5 shadow-md hover:border-white/10 hover:bg-[#1C1C1E]/80 hover:-translate-y-0.5 transition-all cursor-pointer group">
                        <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-white/70 group-hover:text-white transition-colors">
                            <DocumentTextIcon className="w-6 h-6" />
                        </div>
                        <div className="flex-1 mt-1">
                            <h3 className="text-[15px] font-medium text-white/90 group-hover:text-white transition-colors">{doc.title}</h3>
                            <div className="flex items-center gap-3 mt-1.5 text-[11px] text-white/50">
                                <span>{doc.date}</span>
                                <span className="w-1 h-1 rounded-full bg-white/20"></span>
                                <span className="uppercase">{doc.type}</span>
                                <span className="w-1 h-1 rounded-full bg-white/20"></span>
                                <span>{doc.size}</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
