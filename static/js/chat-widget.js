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
    /*
     * True when the connection has dropped. The customer is told; the draft is kept.
     *
     * Their message is the thing that must not disappear quietly — they are mid-problem, and
     * a Send button that swallows what they wrote is worse than one that refuses it.
     */
    connectionLost: false,
    position: null,
    heartbeatTimer: null,
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
        clearInterval(this.heartbeatTimer);
        // Not when the conversation ended normally: that is the socket closing because the
        // chat is over, and telling somebody the connection dropped would be a lie.
        if (this.stage !== "ended") {
          this.stage = "waiting";
          this.connectionLost = true;
        }
      };

      this.socket.onopen = () => {
        this.connectionLost = false;
      };

      this.startHeartbeat();
    },

    /*
     * A customer reading a long reply sends nothing for minutes, and the server cannot tell
     * that apart from a phone that went into a tunnel. Without this they are swept as
     * disconnected mid-conversation (FR-033) while sitting right there — and the agent is
     * told they left.
     *
     * Twenty seconds against a sixty-second grace period: two heartbeats may be lost before
     * anyone is considered gone.
     */
    startHeartbeat() {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = setInterval(() => {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
          this.socket.send(JSON.stringify({ type: "heartbeat" }));
        }
      }, 20000);
    },

    handleControlFrame(frame) {
      if (frame.type === "desk_closed") {
        // The last agent went offline while this visitor waited. Move them to the request
        // form with what they already typed, rather than leaving them watching a position
        // that is accurate and will never change again (FR-042).
        const params = new URLSearchParams(frame.carry || {});
        window.location = `${frame.fallback}?${params}`;
        return;
      }
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
      if (!text) return;

      /*
       * `readyState`, not just `this.socket`. A socket that has closed is still an object, and
       * calling `send` on one throws `InvalidStateError` — so a customer pressing Send on a
       * dropped connection got no reply, no error, and no indication their message had not
       * been delivered. `signalTyping` below has always checked this; the call carrying the
       * customer's actual words did not.
       */
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        this.connectionLost = true;
        return; // the draft is deliberately kept, so nothing they wrote is lost
      }

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
