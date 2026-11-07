import { useState } from "react";
import Header from "./components/Header";
import ChatWindow from "./components/ChatWindow";
import ChatInput from "./components/ChatInput";
import ErrorBanner from "./components/ErrorBanner";
import AppointmentsPanel from "./components/AppointmentsPanel";
import ClinicInfoCard from "./components/ClinicInfoCard";
import { useChat } from "./hooks/useChat";

export default function App() {
  const chat = useChat();
  const [tab, setTab] = useState("chat"); // used on small screens

  return (
    <div className="app">
      <Header onReset={chat.reset} tab={tab} setTab={setTab} />
      <div className={`layout show-${tab}`}>
        <main className="chat-panel">
          <ChatWindow messages={chat.messages} loading={chat.loading} onSend={chat.send} />
          <ErrorBanner message={chat.error} onDismiss={() => chat.setError(null)} />
          <ChatInput onSend={chat.send} disabled={chat.loading} />
          <p className="disclaimer">
            The receptionist can't give medical advice. In an emergency, contact your local emergency services.
          </p>
        </main>
        <aside className="side-panel">
          <AppointmentsPanel
            sessionId={chat.sessionId}
            refreshKey={chat.appointmentsVersion}
            onChanged={chat.refreshAppointments}
          />
          <ClinicInfoCard />
        </aside>
      </div>
    </div>
  );
}
