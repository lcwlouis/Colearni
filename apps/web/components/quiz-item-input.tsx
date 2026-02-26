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
        {item.choices.map((choice) => (
          <label key={choice.id} className="quiz-choice">
            <input
              type="radio"
              name={`item-${item.item_id}`}
              checked={value === choice.id}
              onChange={() => onChange(item.item_id, choice.id)}
            />
            <span>{choice.text}</span>
          </label>
        ))}
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
