const QUESTIONS = [
  "What treatments do you offer?",
  "Show me your doctors",
  "I'd like to book an appointment",
  "What are your opening hours?",
];

export default function SuggestedQuestions({ onPick, disabled }) {
  return (
    <div className="suggestions">
      {QUESTIONS.map((q) => (
        <button key={q} className="chip" disabled={disabled} onClick={() => onPick(q)}>
          {q}
        </button>
      ))}
    </div>
  );
}
