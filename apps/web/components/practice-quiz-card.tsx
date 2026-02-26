import type { PracticeQuizSubmitResponse, QuizFeedbackItem } from "@/lib/api/types";
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
        : "Keep practising — review the feedback above.";
}

/** Strip leading numbering like "1. " or "2) " from a prompt to avoid double-numbering */
function stripLeadingNumber(text: string): string {
    return text.replace(/^\d+[\.\)]\s*/, "");
}

function feedbackForItem(result: PracticeQuizSubmitResponse | null, itemId: number): QuizFeedbackItem | undefined {
    return result?.items.find((fb) => fb.item_id === itemId);
}

function resultClass(fb: QuizFeedbackItem | undefined): string {
    if (!fb) return "";
    return fb.is_correct ? " correct" : " incorrect";
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
                        {quiz.items.map((item) => {
                            const fb = feedbackForItem(result, item.item_id);
                            return (
                                <li key={item.item_id} className={`quiz-item${resultClass(fb)}`}>
                                    <p><strong>{item.position}. {stripLeadingNumber(item.prompt)}</strong></p>
                                    <p className="field-label">Type: {item.item_type}</p>
                                    <QuizItemInput
                                        item={item}
                                        value={answers[item.item_id] ?? ""}
                                        disabled={phase === "submitting_quiz" || phase === "quiz_submitted"}
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
                        </div>
                    ) : null}
                </div>
            ) : null}
        </section>
    );
}
