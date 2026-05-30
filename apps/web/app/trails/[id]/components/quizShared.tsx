"use client";

import type { QuizAttempt } from "@/lib/types";

import { QuizMarkdown } from "./QuizMarkdown";

export function formatQuestionType(
  type: QuizAttempt["questions"][number]["type"],
): string {
  switch (type) {
    case "multiple_choice":
      return "multiple choice";
    case "multi_select":
      return "select all that apply";
    case "ordering":
      return "ordering";
    case "cloze":
      return "fill in the blank";
    case "short_answer":
      return "short answer";
    case "long_answer":
      return "long answer";
    case "code":
      return "code";
  }
}

export function formatQuizType(type: QuizAttempt["quiz_type"]): string {
  return type === "level_up" ? "Level-up" : "Practice";
}

export function formatMasteryStatus(status: string): string {
  return status.replace("_", " ").replace(/^./, (char) => char.toUpperCase());
}

export function formatAttemptDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "recently";
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function humanizeLabel(label: string): string {
  return label
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function questionScoreBand(score: number): {
  label: string;
  className: string;
} {
  if (score >= 0.85) {
    return {
      label: "Strong",
      className: "border-green-200 bg-green-50 text-green-700",
    };
  }
  if (score >= 0.7) {
    return {
      label: "Good",
      className: "border-green-200 bg-green-50 text-green-700",
    };
  }
  if (score >= 0.4) {
    return {
      label: "Partial",
      className: "border-amber-200 bg-amber-50 text-amber-700",
    };
  }
  return {
    label: "Needs work",
    className: "border-red-200 bg-red-50 text-red-700",
  };
}

/** Show only the leading "overall" paragraph, hiding legacy per-question sections. */
export function displayOverallFeedback(feedback: string): string {
  const firstSection = feedback.split(
    /\n{2,}(?=[A-Za-z0-9_ -]{2,40}:\s)/,
  )[0];
  return firstSection.trim() || feedback;
}

/** Render grader feedback, bolding any leading `label:` prefix and rendering math/code. */
export function FormattedFeedback({
  text,
  compact = false,
}: {
  text: string;
  compact?: boolean;
}) {
  const markdown = text
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((paragraph) => {
      const labelled = paragraph.match(/^([A-Za-z0-9_ -]{2,40}):\s*([\s\S]+)$/);
      if (labelled) {
        return `**${humanizeLabel(labelled[1])}:** ${labelled[2]}`;
      }
      return paragraph;
    })
    .join("\n\n");
  if (!markdown) {
    return null;
  }
  return (
    <QuizMarkdown
      text={markdown}
      className={`${compact ? "mt-1" : "mt-2"} text-sm leading-6 text-slate-700`}
    />
  );
}

/** Read-only review of a single graded attempt: feedback, prompts, and answers. */
export function AttemptReview({ attempt }: { attempt: QuizAttempt }) {
  const answerById = Object.fromEntries(
    attempt.answers.map((answer) => [answer.question_id, answer.answer]),
  );

  return (
    <div className="space-y-4 border-t border-slate-200 px-3 py-3">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Feedback
        </p>
        <FormattedFeedback text={attempt.evaluator_feedback} compact />
      </div>
      <ol className="space-y-3">
        {attempt.questions.map((question, index) => {
          const answer = answerById[question.id] || "No answer recorded.";
          const multiline =
            question.type === "code" ||
            question.type === "multi_select" ||
            question.type === "ordering" ||
            question.type === "cloze";
          return (
            <li
              key={question.id}
              className="rounded-md bg-slate-50 p-3 ring-1 ring-slate-200"
            >
              <div className="font-medium text-slate-900">
                <span className="mr-1">{index + 1}.</span>
                <QuizMarkdown
                  text={question.prompt}
                  className="inline-block align-top"
                />
              </div>
              <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                {formatQuestionType(question.type)} ·{" "}
                {question.difficulty ?? "standard"}
              </p>
              <div className="mt-2 rounded-md bg-white p-2 text-slate-700 ring-1 ring-slate-200">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Your answer
                </span>
                {question.type === "code" ? (
                  <pre className="mt-1 overflow-x-auto rounded bg-slate-950 p-2 font-mono text-xs text-slate-100">
                    {answer}
                  </pre>
                ) : (
                  <p className="mt-1 whitespace-pre-line">
                    {multiline
                      ? answer
                          .split("\n")
                          .map((line) => `• ${line}`)
                          .join("\n")
                      : answer}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** A collapsible list of prior attempts, each expandable into a full review. */
export function QuizAttemptList({ attempts }: { attempts: QuizAttempt[] }) {
  return (
    <ol className="space-y-2">
      {attempts.map((attempt) => (
        <li key={attempt.id}>
          <details className="group rounded-lg border border-slate-200 bg-white text-sm">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 marker:hidden">
              <div>
                <p className="font-medium text-slate-800">
                  {formatQuizType(attempt.quiz_type)} ·{" "}
                  {formatAttemptDate(attempt.created_at)}
                </p>
                <p className="text-xs text-slate-500">
                  {attempt.passed ? "Mastery confirmed" : "Review recommended"} ·
                  Click to review
                </p>
              </div>
              <span className="rounded-full bg-slate-50 px-2 py-0.5 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">
                {Math.round(attempt.score * 100)}%
              </span>
            </summary>
            <AttemptReview attempt={attempt} />
          </details>
        </li>
      ))}
    </ol>
  );
}
