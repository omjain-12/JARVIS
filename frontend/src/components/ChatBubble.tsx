import React, { useState } from "react";
import type { ChatMessage } from "@/types";
import { confirmAction } from "@/services/api";
import {
  EnvelopeIcon,
  ChatBubbleOvalLeftEllipsisIcon,
  PhoneIcon,
  PaperAirplaneIcon,
  XMarkIcon,
  CheckCircleIcon,
  XCircleIcon,
} from "@heroicons/react/24/outline";

interface ChatBubbleProps {
  message: ChatMessage;
  onUpdateMessage?: (id: string, updates: Partial<ChatMessage>) => void;
}

/** Channel icon map */
const channelConfig: Record<string, { icon: typeof EnvelopeIcon; label: string; color: string }> = {
  email: { icon: EnvelopeIcon, label: "Email", color: "#0078D4" },
  sms: { icon: ChatBubbleOvalLeftEllipsisIcon, label: "SMS", color: "#00A36C" },
  whatsapp: { icon: PhoneIcon, label: "WhatsApp", color: "#25D366" },
};

function ConfirmationCard({
  data,
  messageId,
  onUpdateMessage,
}: {
  data: Record<string, unknown>;
  messageId: string;
  onUpdateMessage?: (id: string, updates: Partial<ChatMessage>) => void;
}) {
  const [status, setStatus] = useState<"pending" | "sending" | "sent" | "cancelled" | "error">("pending");
  const [resultMsg, setResultMsg] = useState("");

  const channel = (data.channel as string) || "email";
  const recipient = (data.recipient as string) || "unknown";
  const subject = (data.subject as string) || "";
  const body = (data.body as string) || "";
  const actionId = (data.action_id as string) || "";
  const toolName = (data.tool_name as string) || "";
  const toolParams = (data.tool_params as Record<string, unknown>) || {};

  const config = channelConfig[channel] || channelConfig.email;
  const Icon = config.icon;

  const handleSend = async () => {
    setStatus("sending");
    let success = false;
    try {
      const result = await confirmAction(actionId, true, toolName, toolParams);
      if (result.status === "success") {
        success = true;
        setStatus("sent");
        setResultMsg(result.message || "Message sent successfully!");
      } else {
        setStatus("error");
        setResultMsg(result.message || "Failed to send.");
      }
    } catch (err) {
      setStatus("error");
      setResultMsg(err instanceof Error ? err.message : "Failed to send.");
    }
    // Update the parent message so it reflects the new state
    onUpdateMessage?.(messageId, {
      content: success ? `✓ ${config.label} sent to ${recipient}` : `✗ Failed to send ${config.label}`,
    });
  };

  const handleCancel = async () => {
    setStatus("cancelled");
    try {
      await confirmAction(actionId, false);
    } catch {
      // Cancellation is best-effort
    }
    setResultMsg("Message was cancelled.");
    onUpdateMessage?.(messageId, {
      content: `Cancelled ${config.label} to ${recipient}.`,
    });
  };

  // Already resolved states
  if (status === "sent") {
    return (
      <div className="flex items-center gap-3 px-4 py-3 rounded-[8px] bg-[#0A3D0A] dark:bg-[#0A3D0A] border border-green-800/30 text-green-300 mt-3">
        <CheckCircleIcon className="w-5 h-5 flex-shrink-0" />
        <span className="text-[14px]">{resultMsg}</span>
      </div>
    );
  }

  if (status === "cancelled") {
    return (
      <div className="flex items-center gap-3 px-4 py-3 rounded-[8px] bg-jarvis-surface border border-jarvis-border text-jarvis-muted mt-3">
        <XCircleIcon className="w-5 h-5 flex-shrink-0" />
        <span className="text-[14px]">{resultMsg}</span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex items-center gap-3 px-4 py-3 rounded-[8px] bg-red-900/20 border border-red-800/30 text-red-300 mt-3">
        <XCircleIcon className="w-5 h-5 flex-shrink-0" />
        <span className="text-[14px]">{resultMsg}</span>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-[10px] border border-jarvis-border bg-jarvis-surface shadow-panel overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-jarvis-border">
        <div
          className="w-8 h-8 rounded-[6px] flex items-center justify-center"
          style={{ backgroundColor: `${config.color}20` }}
        >
          <Icon className="w-4 h-4" style={{ color: config.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-[13px] font-semibold text-jarvis-text">{config.label}</span>
          <span className="text-jarvis-muted text-[12px] ml-2">to {recipient}</span>
        </div>
      </div>

      {/* Subject (email only) */}
      {subject && (
        <div className="px-4 py-2 border-b border-jarvis-border">
          <span className="text-[12px] text-jarvis-muted">Subject: </span>
          <span className="text-[13px] text-jarvis-text font-medium">{subject}</span>
        </div>
      )}

      {/* Body preview */}
      <div className="px-4 py-3">
        <p className="text-[13px] text-jarvis-text/90 leading-relaxed whitespace-pre-wrap max-h-[200px] overflow-y-auto">
          {body}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 px-4 py-3 border-t border-jarvis-border bg-black/5 dark:bg-white/[0.02]">
        <button
          onClick={handleSend}
          disabled={status === "sending"}
          className="flex items-center gap-2 px-4 py-2 rounded-[6px] text-[13px] font-medium transition-all
            bg-[#0078D4] hover:bg-[#106EBE] text-white disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {status === "sending" ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              Sending…
            </>
          ) : (
            <>
              <PaperAirplaneIcon className="w-3.5 h-3.5" />
              Send
            </>
          )}
        </button>
        <button
          onClick={handleCancel}
          disabled={status === "sending"}
          className="flex items-center gap-2 px-4 py-2 rounded-[6px] text-[13px] font-medium transition-all
            bg-transparent hover:bg-jarvis-panel text-jarvis-muted hover:text-jarvis-text border border-jarvis-border
            disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <XMarkIcon className="w-3.5 h-3.5" />
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function ChatBubble({ message, onUpdateMessage }: ChatBubbleProps) {
  const isUser = message.role === "user";
  const confirmationData = message.structured_data?.type === "pending_confirmation" ? message.structured_data : null;

  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"} mb-4 animate-[fadeInUp_0.3s_ease-out]`}>
      {!isUser && (
        <div className="w-10 h-10 rounded flex flex-shrink-0 items-center justify-center mr-4 mt-1">
          <img src="/logo.png" alt="Assistant" className="w-10 h-10 object-contain" />
        </div>
      )}

      <div className={`w-full max-w-[60%] md:max-w-[620px] ${isUser ? "order-1 flex justify-end" : ""}`}>
        <div>
          <div
            className={`
              text-[15px] leading-relaxed whitespace-pre-wrap break-words transition-all duration-150
              ${isUser
                ? "px-[14px] py-[10px] bg-gradient-to-br from-[#5B8CFF] to-[#7B61FF] text-white rounded-[16px] rounded-br-sm shadow-card-hover"
                : "px-[14px] py-[12px] bg-jarvis-surface text-jarvis-text rounded-[14px] rounded-bl-sm shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
              }
            `}
          >
            {/* When a confirmation card is shown, only display the brief intro line */}
            {confirmationData
              ? message.content.split("\n")[0]
              : message.content
            }
          </div>

          {/* Confirmation card for communication actions */}
          {confirmationData && (
            <ConfirmationCard
              data={confirmationData}
              messageId={message.id}
              onUpdateMessage={onUpdateMessage}
            />
          )}
        </div>
      </div>
    </div>
  );
}
