export type LiveTalkEvent =
  | { type: "session.ready"; session_id: string; voice_available: boolean }
  | { type: "stt.final"; text: string }
  | { type: "assistant.thinking" }
  | { type: "assistant.text.delta"; text: string }
  | { type: "assistant.text.final"; text: string }
  | { type: "assistant.audio.chunk"; mime_type: string; audio_base64: string }
  | { type: "assistant.done" }
  | { type: "assistant.interrupted" }
  | { type: "error"; message: string };

interface LiveTalkClientOptions {
  onEvent: (event: LiveTalkEvent) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (message: string) => void;
}

function resolveWsUrl(): string {
  const base = process.env.NEXT_PUBLIC_BACKEND_WS_URL;
  if (base) {
    return `${base.replace(/\/$/, "")}/ws/live-talk`;
  }

  const backendApi = process.env.NEXT_PUBLIC_BACKEND_API_URL;
  if (backendApi) {
    const wsBase = backendApi.replace(/^http/i, "ws").replace(/\/$/, "");
    return `${wsBase}/ws/live-talk`;
  }

  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.hostname}:8001/ws/live-talk`;
  }

  return "ws://localhost:8001/ws/live-talk";
}

export class LiveTalkClient {
  private socket: WebSocket | null = null;
  private readonly options: LiveTalkClientOptions;

  constructor(options: LiveTalkClientOptions) {
    this.options = options;
  }

  connect(): void {
    if (this.socket && this.socket.readyState <= WebSocket.OPEN) {
      return;
    }

    const url = resolveWsUrl();
    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      this.options.onOpen?.();
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data as string) as LiveTalkEvent;
        this.options.onEvent(parsed);
      } catch {
        this.options.onError?.("Failed to parse live-talk event.");
      }
    };

    this.socket.onerror = () => {
      this.options.onError?.("Live-talk socket error.");
    };

    this.socket.onclose = () => {
      this.options.onClose?.();
      this.socket = null;
    };
  }

  disconnect(): void {
    if (!this.socket) return;
    this.socket.close();
    this.socket = null;
  }

  startSession(userId: string, sessionId: string): void {
    this.send({ type: "session.start", user_id: userId, session_id: sessionId });
  }

  sendUtterance(text: string): void {
    this.send({ type: "utterance.final", text });
  }

  sendAudioChunk(audioBase64: string, mimeType: string): void {
    this.send({ type: "audio.chunk", audio_base64: audioBase64, mime_type: mimeType });
  }

  stopAudioInput(): void {
    this.send({ type: "audio.stop" });
  }

  interrupt(): void {
    this.send({ type: "assistant.interrupt" });
  }

  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  private send(payload: Record<string, unknown>): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.options.onError?.("Live-talk socket is not connected.");
      return;
    }
    this.socket.send(JSON.stringify(payload));
  }
}
