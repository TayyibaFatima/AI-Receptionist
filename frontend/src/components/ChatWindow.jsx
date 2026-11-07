import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import SuggestedQuestions from "./SuggestedQuestions";

const WELCOME =
  "Welcome to Luméra Aesthetics! I'm your virtual receptionist. I can tell you about our treatments, " +
  "introduce our doctors, and help you book, reschedule or cancel an appointment. How can I help you today?";

export default function ChatWindow({ messages, loading, onSend }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  const lastIndex = messages.length - 1;
  const hasUserMessage = messages.some((m) => m.role === "user");

  return (
    <div className="chat-window" role="log" aria-live="polite">
      <MessageBubble message={{ role: "assistant", content: WELCOME, cards: [] }} onSend={onSend} interactive={false} />
      {!hasUserMessage && <SuggestedQuestions onPick={onSend} disabled={loading} />}
      {messages.map((m, i) => (
        <MessageBubble key={m.key} message={m} onSend={onSend} interactive={i === lastIndex && !loading} isLatest={i === lastIndex} />
      ))}
      {loading && <TypingIndicator />}
      <div ref={endRef} />
    </div>
  );
}
