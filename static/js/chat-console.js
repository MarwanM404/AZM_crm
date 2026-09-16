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
function chatConsole(initialUnread, initiallyOnline) {
  return {
    unread: initialUnread || {},
    // Whatever the server says, not a guess. Presence lives in Redis and expires on its own,
    // so the page load is the only moment this side can learn the truth.
    online: Boolean(initiallyOnline),
    refusal: "",
    socket: null,
    heartbeatTimer: null,
    /*
     * Whether the realtime connection is up. Reported as "the go online button doesn't work":
     * the handshake failed, `toggleOnline` returned silently because the socket was not OPEN,
     * and nothing on the page said so. An agent can sit here all morning believing they are
     * reachable while customers queue on the other side.
     *
     * Starts `false` and is set by `onopen`, so the page is honest before the handshake
     * finishes rather than optimistic.
     */
    connected: false,

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

      this.socket.onopen = () => {
        this.connected = true;
        this.refusal = "";
        this.startHeartbeat();
      };

      /*
       * Both handlers, not just `onclose`. A handshake that is refused outright fires `onerror`
       * and then `onclose`; one that drops later fires only `onclose`. Handling one of the two
       * covers one of the two ways this fails.
       */
      this.socket.onerror = () => this.lostConnection();
      this.socket.onclose = () => this.lostConnection();
    },

    lostConnection() {
      this.connected = false;
      this.online = false;
      clearInterval(this.heartbeatTimer);
      this.refusal = gettext(
        "Live chat is not connected, so you cannot go online. Reload the page; if it keeps " +
          "happening, the chat service is down and an administrator needs to know."
      );
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
      /*
       * Says so rather than returning. This used to be a bare `return`, which is what made the
       * button appear broken: pressing it did nothing, showed nothing, and left the agent with
       * no way to tell a broken product from a service that is not running.
       */
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        this.lostConnection();
        return;
      }
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
