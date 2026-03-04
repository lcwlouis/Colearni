import type { QuizItemSummary } from "@/lib/api/types";

type Props = {
  item: QuizItemSummary;
  value: string;
  disabled: boolean;
  onChange: (itemId: number, value: string) => void;
};

export function QuizItemInput({ item, value, disabled, onChange }: Props) {
  if (item.item_type === "short_answer") {
    return (
      <textarea
        rows={3}
        value={value}
        onChange={(event) => onChange(item.item_id, event.target.value)}
        disabled={disabled}
        placeholder="Write your answer"
      />
    );
  }

  if (item.choices?.length) {
    return (
      <fieldset className="quiz-choices" disabled={disabled}>
        <legend className="field-label">Choose one answer</legend>
        {item.choices.map((choice, idx) => {
          const isSelected = value === choice.id;
          const letter = String.fromCharCode(65 + idx); // A, B, C, D...
          return (
            <button
              key={choice.id}
              type="button"
              className={`quiz-choice-card${isSelected ? " selected" : ""}`}
              onClick={() => { if (!disabled) onChange(item.item_id, choice.id); }}
              disabled={disabled && !isSelected}
            >
              <span className="quiz-choice-letter">{letter}</span>
              <span className="quiz-choice-text">{choice.text}</span>
              {isSelected && <span className="quiz-choice-check">✓</span>}
            </button>
          );
        })}
      </fieldset>
    );
  }

  return (
    <input
      type="text"
      value={value}
      onChange={(event) => onChange(item.item_id, event.target.value)}
      disabled={disabled}
      placeholder="Enter choice id"
    />
  );
}
