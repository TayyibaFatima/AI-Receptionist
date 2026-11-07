import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";
import RescheduleModal from "./RescheduleModal";

const fmtDate = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });

const fmtTime = (hhmm) => {
  const [h, m] = hhmm.split(":").map(Number);
  const d = new Date();
  d.setHours(h, m, 0, 0);
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
};

export default function AppointmentsPanel({ sessionId, refreshKey, onChanged }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [rescheduling, setRescheduling] = useState(null);
  const [confirmCancel, setConfirmCancel] = useState(null);

  const load = useCallback(async () => {
    try {
      setItems(await api.getAppointments(sessionId));
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load, refreshKey]);

  const cancel = async (id) => {
    try {
      await api.cancelAppointment(sessionId, id);
      setConfirmCancel(null);
      await load();
      onChanged();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="panel-card">
      <h3>My appointments</h3>
      {error && <p className="error-text">{error}</p>}
      {loading && <p className="muted">Loading…</p>}
      {!loading && items.length === 0 && (
        <p className="muted">No appointments yet. Ask the receptionist to book one for you.</p>
      )}
      <ul className="appt-list">
        {items.map((a) => (
          <li key={a.id} className="appt">
            <div className="appt-head">
              <strong>{a.service_name || a.appointment_type_label}</strong>
              <span className="tag">#{a.id}</span>
            </div>
            <p>{a.doctor_name}</p>
            <p className="muted">{fmtDate(a.appointment_date)} · {fmtTime(a.appointment_time)}</p>
            {confirmCancel === a.id ? (
              <div className="actions">
                <button className="btn danger small" onClick={() => cancel(a.id)}>Yes, cancel</button>
                <button className="btn ghost small" onClick={() => setConfirmCancel(null)}>Keep it</button>
              </div>
            ) : (
              <div className="actions">
                <button className="btn small" onClick={() => setRescheduling(a)}>Reschedule</button>
                <button className="btn ghost small" onClick={() => setConfirmCancel(a.id)}>Cancel</button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {rescheduling && (
        <RescheduleModal
          appointment={rescheduling}
          sessionId={sessionId}
          onClose={() => setRescheduling(null)}
          onDone={() => {
            setRescheduling(null);
            load();
            onChanged();
          }}
        />
      )}
    </div>
  );
}
