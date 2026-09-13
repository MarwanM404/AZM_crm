/*
 * The agent's console.
 *
 * ADR-008 named this file's job as the one place the htmx-over-WebSocket approach is
 * strained: unread counts span several conversations and outlive any single fragment, so they
 * cannot be server-rendered HTML swapped into the DOM. They arrive as a small JSON control
 * frame beside the HTML ones, and this holds them.
 *
 * Everything else the console shows is still rendered by the server. If this file starts
 * building markup, that is the signal ADR-008 asked to watch for.
 */
function chatConsole(initialUnread) {
  return {
    unread: initialUnread || {},
    online: false,
    refusal: "",
    socket: null,
    heartbeatTimer: null,

    init() {
      this.connect();
    },

    get statusLabel() {
      return this.online ? gettext("Online") : gettext("Offline");
    },

    connect() {
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      this.socket = new WebSocket(`${scheme}://${window.location.host}/ws/chat/agent/`);

      this.socket.onmessage = (event) => {
        const text = event.data;
        if (!text.startsWith("{")) {
          // Rendered HTML for the open conversation, if one is on screen.
          const thread = document.getElementById("chat-thread");
          if (thread) {
            thread.insertAdjacentHTML("beforeend", text);
            thread.scrollTop = thread.scrollHeight;
          }
          return;
        }
        this.handleControlFrame(JSON.parse(text));
      };

      this.socket.onopen = () => this.startHeartbeat();
      this.socket.onclose = () => {
        this.online = false;
        clearInterval(this.heartbeatTimer);
      };
    },

    handleControlFrame(frame) {
      switch (frame.type) {
        case "unread":
          // Replaced wholesale rather than incremented: the server's count is the truth, and
          // a client that counts for itself drifts the moment a frame is missed.
          this.unread = frame.counts || {};
          break;
        case "offline_refused":
          // FR-014. The number matters: "you still have conversations open" is unactionable.
          this.refusal = interpolate(
            gettext("You still have %s conversation(s) open."),
            [frame.open]
          );
          break;
        case "offline":
          this.online = false;
          this.refusal = "";
          break;
        case "assigned":
          window.location.reload(); // a new conversation changes the list the server rendered
          break;
      }
    },

    toggleOnline() {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
      this.refusal = "";
      if (this.online) {
        this.socket.send(JSON.stringify({ type: "offline" }));
      } else {
        this.socket.send(JSON.stringify({ type: "online" }));
        this.online = true;
      }
    },

    startHeartbeat() {
      clearInterval(this.heartbeatTimer);
      // Presence expires on its own if this stops, which is the point: a console that died
      // stops being counted as an available agent without anything having to notice.
      this.heartbeatTimer = setInterval(() => {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
          this.socket.send(JSON.stringify({ type: "heartbeat" }));
        }
      }, 20000);
    },
  };
}

/* Django's JavaScript catalog is not wired up for this one screen, so these fall back to the
   source string rather than failing. If more client-side strings appear, that catalog is the
   right next step rather than growing this. */
