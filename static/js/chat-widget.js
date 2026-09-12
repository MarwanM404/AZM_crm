/*
 * The visitor's chat panel.
 *
 * Small on purpose. The socket carries rendered HTML (ADR-008), so this file does not build
 * markup — it appends what the server sent, and holds the little state that outlives any one
 * fragment: which stage we are in, whether the other party is typing, the draft.
 */
function chatWidget() {
  return {
    stage: "form",
    errors: {},
    draft: "",
    position: null,
    reference: null,
    theyAreTyping: false,
    typingTimer: null,
    socket: null,

    async start() {
      const form = this.$el;
      const body = new FormData(form);
      const response = await fetch("/chat/start/", {
        method: "POST",
        body,
        headers: { "X-CSRFToken": body.get("csrfmiddlewaretoken") },
      });
      const data = await response.json();

      if (data.available === false) {
        // The desk closed between loading the page and submitting. Carry what was typed
        // rather than making them write it again (FR-018).
        const params = new URLSearchParams(data.carry || {});
        window.location = `${data.fallback}?${params}`;
        return;
      }
      if (response.status === 422) {
        this.errors = data.errors || {};
        return;
      }

      this.errors = {};
      this.position = data.position;
      this.stage = data.assigned ? "chatting" : "waiting";
      this.connect(data.token);
    },

    connect(token) {
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      this.socket = new WebSocket(
        `${scheme}://${window.location.host}/ws/chat/visitor/?token=${encodeURIComponent(token)}`
      );

      this.socket.onmessage = (event) => {
        const text = event.data;
        if (text.startsWith("{")) {
          this.handleControlFrame(JSON.parse(text));
          return;
        }
        // Rendered HTML from the server: append it, do not interpret it.
        document.getElementById("chat-thread").insertAdjacentHTML("beforeend", text);
        this.scrollToLatest();
      };

      this.socket.onclose = () => {
        if (this.stage !== "ended") this.stage = "waiting";
      };
    },

    handleControlFrame(frame) {
      if (frame.type === "state") {
        this.position = frame.position ?? this.position;
        if (frame.state === "ACTIVE") this.stage = "chatting";
      } else if (frame.type === "typing") {
        this.theyAreTyping = frame.who === "agent";
        clearTimeout(this.typingTimer);
        this.typingTimer = setTimeout(() => (this.theyAreTyping = false), 3000);
      } else if (frame.type === "ended") {
        this.reference = frame.reference || null;
        this.stage = "ended";
      }
    },

    send() {
      const text = this.draft.trim();
      if (!text || !this.socket) return;
      this.socket.send(JSON.stringify({ type: "message", text }));
      this.draft = "";
    },

    signalTyping() {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
      this.socket.send(JSON.stringify({ type: "typing" }));
    },

    scrollToLatest() {
      const thread = document.getElementById("chat-thread");
      thread.scrollTop = thread.scrollHeight;
    },
  };
}
