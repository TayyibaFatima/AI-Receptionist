import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function ClinicInfoCard() {
  const [info, setInfo] = useState(null);
  useEffect(() => {
    api.getClinic().then(setInfo).catch(() => {});
  }, []);
  if (!info) return null;
  return (
    <div className="panel-card clinic-info">
      <h3>Visit us</h3>
      {info.address && <p>{info.address}</p>}
      {info.opening_hours && <p className="muted">{info.opening_hours}</p>}
      {info.phone && <p className="muted">{info.phone}</p>}
    </div>
  );
}
