/*
 * The observer's client (FR-020 to FR-022).
 *
 * Read-only by construction: it opens the socket, appends what arrives, and has no send path
 * at all. The server rejects customer-directed frames anyway (apps/chat/consumers/supervisor.py),
 * but there is nothing here to send one with — the guarantee should not rest on the browser.
 */
function chatObserve(conversationId) {
  return {
    socket: null,
    ended: false,
    draft: "",

    init() {
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      this.socket = new WebSocket(
        `${scheme}://${window.location.host}/ws/chat/supervise/?conversation=${conversationId}`
      );
      this.socket.addEventListener("message", (event) => this.receive(event.data));
    },

    /*
     * The only thing this page can send, and it can only be a private note (FR-027). There is
     * no destination argument and no mode: the frame type is a literal. A bug here cannot
     * turn a note into a customer-facing message, because there is no code path that would
     * produce one.
     */
    sendWhisper() {
      const text = this.draft.trim();
      if (!text || !this.socket) return;
      this.socket.send(JSON.stringify({ type: "whisper", text }));
      this.draft = "";
    },

    receive(data) {
      // Rendered fragments arrive as HTML; control frames as JSON. The server decides which,
      // and decides what an observer may see before it sends anything.
      if (data.startsWith("{")) {
        let payload;
        try {
          payload = JSON.parse(data);
        } catch (error) {
          return;
        }
        if (payload.type === "ended") {
          this.ended = true;
        }
        return;
      }
      const thread = document.getElementById("chat-thread");
      if (thread) {
        thread.insertAdjacentHTML("beforeend", data);
        thread.scrollTop = thread.scrollHeight;
      }
    },
  };
}
