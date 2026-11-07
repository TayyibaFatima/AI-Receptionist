import { useEffect, useState } from "react";
import { api } from "../services/api";

const todayIso = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
};

export default function RescheduleModal({ appointment, sessionId, onClose, onDone }) {
  const [date, setDate] = useState(appointment.appointment_date);
  const [slots, setSlots] = useState([]);
  const [picked, setPicked] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setPicked(null);
    setError(null);
    api
      .getAvailability(appointment.doctor_id, date, appointment.service_id)
      .then((d) => !cancelled && setSlots(d.slots))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [date, appointment.doctor_id, appointment.service_id]);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.rescheduleAppointment(sessionId, appointment.id, date, picked);
      onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h3>Reschedule appointment #{appointment.id}</h3>
        <p className="muted">{appointment.service_name || appointment.appointment_type_label} with {appointment.doctor_name}</p>
        <label className="field">
          New date
          <input type="date" min={todayIso()} value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <div className="slot-grid">
          {slots.length === 0 && !error && <p className="muted">No free slots on this date. Try another day.</p>}
          {slots.map((s) => (
            <button key={s.time} className={`slot ${picked === s.time ? "picked" : ""}`} onClick={() => setPicked(s.time)}>
              {s.display}
            </button>
          ))}
        </div>
        {error && <p className="error-text">{error}</p>}
        <div className="actions">
          <button className="btn primary" disabled={!picked || busy} onClick={confirm}>
            {busy ? "Saving…" : "Confirm new time"}
          </button>
          <button className="btn ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
