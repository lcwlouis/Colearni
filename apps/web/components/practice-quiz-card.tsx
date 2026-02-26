import type { PracticeQuizSubmitResponse } from "@/lib/api/types";
import { QuizItemInput } from "@/components/quiz-item-input";
import { canSubmitPractice, type PracticeState } from "@/lib/practice/practice-state";

type Props = {
    state: PracticeState;
    onAnswerChange: (itemId: number, value: string) => void;
    onSubmitQuiz: () => void;
    onReset: () => void;
};

function practiceFeedbackLabel(result: PracticeQuizSubmitResponse): string {
    if (result.critical_misconception) {
        return "Review the flagged misconception and try again.";
    }
    return result.passed
        ? "Good work! Remember: this is practice only."
        : "Keep practising — review the per-item feedback below.";
}

export function PracticeQuizCard({ state, onAnswerChange, onSubmitQuiz, onReset }: Props) {
    const { phase, quiz, answers, result, error } = state;

    return (
        <section className="panel stack" aria-label="Practice quiz">
            <div className="practice-header">
                <h2>Practice quiz</h2>
                <span className="practice-badge">Practice only — does not affect mastery</span>
            </div>

            {phase === "loading_quiz" ? <p className="status loading">Generating practice quiz...</p> : null}
            {phase === "error" && !quiz ? <p className="status error">Error: {error}</p> : null}

            {quiz ? (
                <div className="stack">
                    <ol className="quiz-items">
                        {quiz.items.map((item) => (
                            <li key={item.item_id} className="quiz-item">
                                <p><strong>{item.position}. {item.prompt}</strong></p>
                                <p className="field-label">Type: {item.item_type}</p>
                                <QuizItemInput
                                    item={item}
                                    value={answers[item.item_id] ?? ""}
                                    disabled={phase === "submitting_quiz" || phase === "quiz_submitted"}
                                    onChange={onAnswerChange}
                                />
                            </li>
                        ))}
                    </ol>

                    {phase !== "quiz_submitted" ? (
                        <div className="button-row">
                            <button type="button" onClick={onSubmitQuiz} disabled={!canSubmitPractice(state) || phase === "submitting_quiz"}>
                                Submit practice
                            </button>
                            <button type="button" className="secondary" onClick={onReset}>Back</button>
                        </div>
                    ) : (
                        <div className="button-row">
                            <button type="button" className="secondary" onClick={onReset}>Back</button>
                        </div>
                    )}

                    {phase === "submitting_quiz" ? <p className="status loading">Grading...</p> : null}
                    {phase === "error" && quiz ? <p className="status error">Submit error: {error}</p> : null}

                    {result ? (
                        <div className="stack practice-feedback">
                            <h3>Practice feedback</h3>
                            <span className="practice-badge">Practice only — does not affect mastery</span>
                            <p>{result.overall_feedback}</p>
                            <p className="field-label">Score: {Math.round(result.score * 100)}%</p>
                            <p className="field-label">{practiceFeedbackLabel(result)}</p>

                            <h3>Per-item feedback</h3>
                            <ul className="quiz-feedback-list">
                                {result.items.map((item) => (
                                    <li key={item.item_id}>
                                        <p><strong>Item {item.item_id}: {item.result}</strong></p>
                                        <p>{item.feedback}</p>
                                        <p className="field-label">
                                            Score: {typeof item.score === "number" ? item.score.toFixed(2) : "n/a"}
                                            {item.critical_misconception ? " · critical misconception" : ""}
                                        </p>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ) : null}
                </div>
            ) : null}
        </section>
    );
}
