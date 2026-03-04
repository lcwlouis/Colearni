import { useState } from "react";
import type { PracticeQuizSubmitResponse, QuizFeedbackItem } from "@/lib/api/types";
import { QuizItemInput } from "@/components/quiz-item-input";
import { canSubmitPractice, type PracticeState } from "@/lib/practice/practice-state";

type Props = {
    state: PracticeState;
    onAnswerChange: (itemId: number, value: string) => void;
    onSubmitQuiz: () => void;
    onReset: () => void;
    onNextQuiz: () => void;
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
    if (fb.is_correct) return " correct";
    // Green style for passing non-MCQ scores
    if (typeof fb.score === "number" && fb.score >= 0.7 && !fb.critical_misconception) return " correct";
    return " incorrect";
}

export function PracticeQuizCard({ state, onAnswerChange, onSubmitQuiz, onReset, onNextQuiz }: Props) {
    const { phase, quiz, answers, result, error } = state;
    const [minimized, setMinimized] = useState(false);

    // Minimized summary card after submission
    if (minimized && result) {
        const scorePercent = Math.round(result.score * 100);
        return (
            <section className="panel practice-minimized" aria-label="Practice quiz result">
                <div className="practice-minimized-row">
                    <span className={`practice-minimized-score ${result.passed ? "passed" : "failed"}`}>
                        {scorePercent}%
                    </span>
                    <span className="practice-minimized-label">
                        Practice quiz {result.passed ? "passed" : "needs review"}
                    </span>
                    <div className="button-row">
                        <button type="button" className="secondary" onClick={() => setMinimized(false)}>
                            Expand
                        </button>
                        <button type="button" onClick={onNextQuiz}>Next Quiz</button>
                        <button type="button" className="secondary" onClick={onReset}>Close</button>
                    </div>
                </div>
            </section>
        );
    }

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
                                            <span className={`quiz-item-result-label ${fb.is_correct || (typeof fb.score === "number" && fb.score >= 0.7 && !fb.critical_misconception) ? "correct" : "incorrect"}`}>
                                                {fb.is_correct || (typeof fb.score === "number" && fb.score >= 0.7 && !fb.critical_misconception) ? "✓ Correct" : "✗ Incorrect"}
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
                            <button type="button" className="secondary" onClick={onReset}>End practice</button>
                        </div>
                    ) : (
                        <div className="button-row">
                            <button type="button" onClick={onNextQuiz}>Next Quiz</button>
                            <button type="button" className="secondary" onClick={() => setMinimized(true)}>Minimize</button>
                            <button type="button" className="secondary" onClick={onReset}>End practice</button>
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
