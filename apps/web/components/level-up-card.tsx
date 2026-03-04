import type { LevelUpQuizSubmitResponse, QuizFeedbackItem } from "@/lib/api/types";
import { QuizItemInput } from "@/components/quiz-item-input";
import { canSubmitLevelUp, type LevelUpState } from "@/lib/tutor/level-up-state";

type Props = {
  state: LevelUpState;
  onStartQuiz: () => void;
  onAnswerChange: (itemId: number, value: string) => void;
  onSubmitQuiz: () => void;
  onRetryCreate: () => void;
  onRetrySubmit: () => void;
  onStartNew: () => void;
};

function nextSteps(result: LevelUpQuizSubmitResponse): string {
  if (result.critical_misconception) {
    return "Review the flagged misconception, then create a new level-up quiz.";
  }
  if (result.passed) {
    return "You passed. Ask for a direct summary when needed, or explore adjacent concepts.";
  }
  if (result.retry_hint) {
    return `You did not pass. ${result.retry_hint}.`;
  }
  return "You did not pass. Review the per-item feedback and retry with a new quiz.";
}

/** Strip leading numbering like "1. " or "2) " from a prompt to avoid double-numbering */
function stripLeadingNumber(text: string): string {
  return text.replace(/^\d+[\.\)]\s*/, "");
}

function feedbackForItem(result: LevelUpQuizSubmitResponse | null, itemId: number): QuizFeedbackItem | undefined {
  return result?.items.find((fb) => fb.item_id === itemId);
}

function resultClass(fb: QuizFeedbackItem | undefined): string {
  if (!fb) return "";
  return fb.is_correct ? " correct" : " incorrect";
}

export function LevelUpCard({
  state,
  onStartQuiz,
  onAnswerChange,
  onSubmitQuiz,
  onRetryCreate,
  onRetrySubmit,
  onStartNew,
}: Props) {
  const { phase, quiz, answers, result, error } = state;

  return (
    <section className="panel stack" aria-label="Level-up">
      <h2>Level-up quiz</h2>
      {phase === "idle" ? (
        <div className="button-row">
          <button type="button" onClick={onStartQuiz}>
            Start level-up
          </button>
        </div>
      ) : null}

      {phase === "creating" ? <p className="status loading">Building level-up quiz...</p> : null}

      {phase === "create_error" ? (
        <div className="stack">
          <p className="status error">Could not create level-up quiz: {error}</p>
          <div className="button-row">
            <button type="button" className="secondary" onClick={onRetryCreate}>
              Retry create
            </button>
          </div>
        </div>
      ) : null}

      {quiz ? (
        <div className="stack">
          <ol className="quiz-items">
            {quiz.items.map((item) => {
              const fb = feedbackForItem(result, item.item_id);
              return (
                <li key={item.item_id} className={`quiz-item${resultClass(fb)}`}>
                  <p>
                    <strong>
                      {item.position}. {stripLeadingNumber(item.prompt)}
                    </strong>
                  </p>
                  <p className="field-label">Type: {item.item_type}</p>
                  <QuizItemInput
                    item={item}
                    value={answers[item.item_id] ?? ""}
                    disabled={phase === "submitting" || phase === "submitted"}
                    onChange={onAnswerChange}
                  />
                  {fb ? (
                    <div className="quiz-item-feedback">
                      <span className={`quiz-item-result-label ${fb.is_correct ? "correct" : "incorrect"}`}>
                        {fb.is_correct ? "✓ Correct" : "✗ Incorrect"}
                      </span>
                      <p>{fb.feedback}</p>
                      <p className="field-label">
                        Score: {typeof fb.score === "number" ? fb.score.toFixed(2) : "n/a"}
                        {fb.critical_misconception ? " · critical misconception" : ""}
                      </p>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ol>

          {phase !== "submitted" ? (
            <div className="button-row">
              <button
                type="button"
                onClick={onSubmitQuiz}
                disabled={!canSubmitLevelUp(state) || phase === "submitting"}
              >
                Submit once
              </button>
              <button type="button" className="secondary" onClick={onStartNew}>
                Start new quiz
              </button>
            </div>
          ) : (
            <div className="button-row">
              <button type="button" className="secondary" onClick={onStartNew}>
                Start new quiz
              </button>
            </div>
          )}

          {phase === "submitting" ? <p className="status loading">Submitting and grading...</p> : null}

          {phase === "submit_error" ? (
            <div className="stack">
              <p className="status error">Could not submit level-up quiz: {error}</p>
              <div className="button-row">
                <button
                  type="button"
                  className="secondary"
                  onClick={onRetrySubmit}
                  disabled={!canSubmitLevelUp(state)}
                >
                  Retry submit
                </button>
              </div>
            </div>
          ) : null}

          {result ? (
            <div className="stack level-up-feedback">
              <h3>Overall summary</h3>
              <p>{result.overall_feedback}</p>
              <p className="field-label">
                Score: {Math.round(result.score * 100)}% · Mastery: {result.mastery_status} (
                {Math.round(result.mastery_score * 100)}%)
              </p>
              <p className="field-label">Next step: {nextSteps(result)}</p>
              {result.replayed && result.retry_hint ? (
                <p className="field-label">Replay notice: {result.retry_hint}</p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
