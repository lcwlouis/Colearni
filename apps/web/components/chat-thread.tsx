import type { ChatMessage } from "@/lib/tutor/chat-state";
import { ChatResponse } from "@/components/chat-response";

type Props = {
  messages: ChatMessage[];
  loading: boolean;
};

export function ChatThread({ messages, loading }: Props) {
  if (!messages.length) {
    return <p className="status empty">Start by asking a question.</p>;
  }

  return (
    <div className="chat-thread" aria-live="polite">
      {messages.map((message) => (
        <article
          key={message.id}
          className={`chat-message ${message.role === "user" ? "user" : "assistant"}`}
        >
          <p className="chat-role">{message.role === "user" ? "You" : "Tutor"}</p>
          {message.role === "user" ? (
            <p className="chat-text">{message.text}</p>
          ) : (
            <ChatResponse response={message.response} />
          )}
        </article>
      ))}
      {loading ? <p className="status loading">Tutor is responding...</p> : null}
    </div>
  );
}
