export default function Header({ onReset, tab, setTab }) {
  return (
    <header className="header">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">L</div>
        <div>
          <h1>Luméra Aesthetics</h1>
          <p>Virtual Receptionist</p>
        </div>
      </div>
      <nav className="tabs" aria-label="Sections">
        <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>Chat</button>
        <button className={tab === "appointments" ? "active" : ""} onClick={() => setTab("appointments")}>
          My appointments
        </button>
      </nav>
      <button className="btn ghost" onClick={onReset} title="Start a new conversation">
        New conversation
      </button>
    </header>
  );
}
