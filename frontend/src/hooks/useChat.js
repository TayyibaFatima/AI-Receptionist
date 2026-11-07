import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../services/api";

const STORAGE_KEY = "lumera_session_id";

function newId() {
  return crypto.randomUUID();
}

function loadSessionId() {
  try {
    let id = localStorage.getItem(STORAGE_KEY);
    if (!id) {
      id = newId();
      localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    return newId();
  }
}

export function useChat() {
  const [sessionId, setSessionId] = useState(loadSessionId);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [appointmentsVersion, setAppointmentsVersion] = useState(0);
  const counter = useRef(0);
  const nextKey = () => `m${++counter.current}`;

  // Restore this visitor's earlier conversation from PostgreSQL.
  useEffect(() => {
    let cancelled = false;
    api
      .getHistory(sessionId)
      .then((rows) => {
        if (cancelled) return;
        setMessages(rows.map((m) => ({ key: nextKey(), role: m.role, content: m.content, cards: [] })));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const send = useCallback(
    async (text) => {
      const content = text.trim();
      if (!content || loading) return;
      setError(null);
      setMessages((prev) => [...prev, { key: nextKey(), role: "user", content, cards: [] }]);
      setLoading(true);
      try {
        const data = await api.sendChat(sessionId, content);
        setMessages((prev) => [
          ...prev,
          { key: nextKey(), role: "assistant", content: data.reply, cards: data.cards || [] },
        ]);
        if (data.appointments_changed) setAppointmentsVersion((v) => v + 1);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [sessionId, loading]
  );

  const reset = useCallback(() => {
    const id = newId();
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* ignore */
    }
    setMessages([]);
    setError(null);
    setSessionId(id);
    setAppointmentsVersion((v) => v + 1);
  }, []);

  const refreshAppointments = useCallback(() => setAppointmentsVersion((v) => v + 1), []);

  return { sessionId, messages, loading, error, setError, send, reset, appointmentsVersion, refreshAppointments };
}
