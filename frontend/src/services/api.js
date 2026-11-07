const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", body, sessionId } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (sessionId) headers["X-Session-ID"] = sessionId;

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("I can't reach the server right now. Please check your connection and try again.", 0);
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    /* empty body */
  }

  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    if (data && typeof data.detail === "string") message = data.detail;
    else if (response.status === 422) message = "Please check the details and try again.";
    else if (response.status === 429) message = "Too many messages. Please wait a moment.";
    throw new ApiError(message, response.status);
  }
  return data;
}

export const api = {
  sendChat: (sessionId, message) => request("/chat", { method: "POST", body: { session_id: sessionId, message } }),
  getHistory: (sessionId) => request("/chat/history", { sessionId }),
  getClinic: () => request("/clinic"),
  getAppointments: (sessionId) => request("/appointments", { sessionId }),
  cancelAppointment: (sessionId, id) =>
    request(`/appointments/${id}?confirmed=true`, { method: "DELETE", sessionId }),
  rescheduleAppointment: (sessionId, id, date, time) =>
    request(`/appointments/${id}`, {
      method: "PATCH",
      sessionId,
      body: { appointment_date: date, appointment_time: time, confirmed: true },
    }),
  getAvailability: (doctorId, date, serviceId) =>
    request(`/availability?doctor_id=${doctorId}&date=${date}${serviceId ? `&service_id=${serviceId}` : ""}`),
};
