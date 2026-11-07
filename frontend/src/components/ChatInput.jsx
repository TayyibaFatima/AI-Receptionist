import { useState } from "react";

export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState("");

  const submit = (e) => {
    e.preventDefault();
    if (!value.trim() || disabled) return;
    onSend(value);
    setValue("");
  };

  return (
    <form className="chat-input" onSubmit={submit}>
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask about treatments, doctors or booking…"
        maxLength={1000}
        aria-label="Message"
        autoComplete="off"
      />
      <button className="btn primary" type="submit" disabled={disabled || !value.trim()}>
        Send
      </button>
    </form>
  );
}
