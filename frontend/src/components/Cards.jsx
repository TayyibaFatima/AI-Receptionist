const price = (value, currency) => (value == null ? null : `${currency} ${Number(value).toLocaleString()}`);

const GROUPS = [
  ["aesthetic_treatment", "Aesthetic treatments"],
  ["general_consultation", "Doctor consultations"],
];

function ServiceCard({ s, currency, onSend, disabled }) {
  return (
    <div className="card">
      <h4>{s.name}</h4>
      {s.description && <p className="muted">{s.description}</p>}
      <p className="meta">
        {price(s.price, currency) || "Price on request"}
        {s.duration_minutes ? ` · ${s.duration_minutes} min` : ""}
      </p>
      <button className="btn small" disabled={disabled} onClick={() => onSend(`I'd like the ${s.name}.`)}>
        Choose
      </button>
    </div>
  );
}

export function ServiceCards({ card, onSend, disabled }) {
  return (
    <div className="service-groups">
      {GROUPS.map(([category, title]) => {
        const items = card.items.filter((s) => s.category === category);
        if (items.length === 0) return null;
        return (
          <section key={category}>
            <h5 className="group-title">{title}</h5>
            <div className="card-grid">
              {items.map((s) => (
                <ServiceCard key={s.id} s={s} currency={card.currency} onSend={onSend} disabled={disabled} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

export function DoctorCards({ card, onSend, disabled }) {
  return (
    <div className="card-grid">
      {card.items.map((d) => (
        <div className="card" key={d.id}>
          <span className="tag">{d.specialization}</span>
          <h4>{d.name}</h4>
          {d.profile && <p className="muted">{d.profile}</p>}
          <p className="meta">
            {d.consultation_fee != null ? `Consultation ${price(d.consultation_fee, card.currency)}` : "Fee not listed"}
          </p>
          <button className="btn small" disabled={disabled} onClick={() => onSend(`I'd like to book with ${d.name}.`)}>
            Choose doctor
          </button>
        </div>
      ))}
    </div>
  );
}

export function SlotCards({ card, onSend, disabled }) {
  return (
    <div className="card wide">
      <h4>{card.doctor_name}</h4>
      <p className="muted">{card.date_display}</p>
      <div className="slot-grid">
        {card.slots.map((s) => (
          <button
            key={s.time}
            className="slot"
            disabled={disabled}
            onClick={() => onSend(`I'll take the ${s.display} slot on ${card.date_display}.`)}
          >
            {s.display}
          </button>
        ))}
      </div>
    </div>
  );
}

const CONFIRM_TEXT = {
  create: ["Confirm appointment", "Yes, please confirm this appointment."],
  reschedule: ["Confirm change", "Yes, please confirm this change."],
  cancel: ["Yes, cancel it", "Yes, please cancel it."],
};

export function ConfirmationCard({ card, onSend, disabled }) {
  const [label, yes] = CONFIRM_TEXT[card.action] || CONFIRM_TEXT.create;
  return (
    <div className="card wide summary">
      <h4>{card.title}</h4>
      <dl>
        {card.rows.map((r) => (
          <div key={r.label}>
            <dt>{r.label}</dt>
            <dd>{r.value}</dd>
          </div>
        ))}
      </dl>
      <div className="actions">
        <button className="btn primary" disabled={disabled} onClick={() => onSend(yes)}>{label}</button>
        <button className="btn ghost" disabled={disabled} onClick={() => onSend("No, I'd like to change something.")}>
          Change something
        </button>
      </div>
    </div>
  );
}

export function BookedCard({ card }) {
  return (
    <div className="card wide summary success">
      <h4>✓ {card.title}</h4>
      <p className="muted">Reference #{card.appointment_id}</p>
      <dl>
        {card.rows.map((r) => (
          <div key={r.label}>
            <dt>{r.label}</dt>
            <dd>{r.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function AppointmentListCard({ card }) {
  return (
    <div className="card wide">
      <h4>Your appointments</h4>
      <ul className="plain-list">
        {card.items.map((a) => (
          <li key={a.id}>
            <strong>#{a.id}</strong> {a.service_name || a.appointment_type_label} with {a.doctor_name}
            <br />
            <span className="muted">{a.date_display}, {a.time_display} · {a.status}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function CardRenderer({ card, onSend, disabled }) {
  switch (card.type) {
    case "services": return <ServiceCards card={card} onSend={onSend} disabled={disabled} />;
    case "doctors": return <DoctorCards card={card} onSend={onSend} disabled={disabled} />;
    case "slots": return <SlotCards card={card} onSend={onSend} disabled={disabled} />;
    case "confirmation": return <ConfirmationCard card={card} onSend={onSend} disabled={disabled} />;
    case "booked": return <BookedCard card={card} />;
    case "appointments": return <AppointmentListCard card={card} />;
    default: return null;
  }
}
