import CardRenderer from "./Cards";

// Old browse cards (services, doctors, slots) are hidden once the chat moves on, to keep the thread clean.
const KEEP_WHEN_OLD = new Set(["booked", "appointments"]);

export default function MessageBubble({ message, onSend, interactive, isLatest }) {
  const isUser = message.role === "user";
  const cards = (message.cards || []).filter((c) => isLatest || KEEP_WHEN_OLD.has(c.type));
  return (
    <div className={`bubble-row ${isUser ? "user" : "assistant"}`}>
      {!isUser && <div className="avatar" aria-hidden="true">L</div>}
      <div className="bubble-col">
        <div className={`bubble ${isUser ? "user" : "assistant"}`}>{message.content}</div>
        {cards.map((card, i) => (
          <CardRenderer key={i} card={card} onSend={onSend} disabled={!interactive} />
        ))}
      </div>
    </div>
  );
}
