"use client";

import { useEffect, useState } from "react";

import {
  generateLevelUpQuiz,
  generatePracticeQuiz,
  gradeLevelUpQuiz,
  gradePracticeQuiz,
} from "@/lib/api";
import type { GradeResult, LevelUpCard, MasteryStatus, QuizAnswer } from "@/lib/types";

type QuizState = "loading" | "answering" | "grading" | "result";

const quizGenerationRequests = new Map<string, Promise<LevelUpCard>>();

interface QuizPanelProps {
  workspaceId: string;
  trailId: string;
  conceptId: string;
  mode: "level_up" | "practice";
  onBack: () => void;
  onMasteryUpdated?: (conceptId: string, update: { status: MasteryStatus; score: number }) => void;
}

export function QuizPanel({
  workspaceId,
  trailId,
  conceptId,
  mode,
  onBack,
  onMasteryUpdated,
}: QuizPanelProps) {
  const [quizState, setQuizState] = useState<QuizState>("loading");
  const [card, setCard] = useState<LevelUpCard | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<GradeResult | null>(null);
  const [generateError, setGenerateError] = useState("");
  const [gradeError, setGradeError] = useState("");
  const [retryTrigger, setRetryTrigger] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setQuizState("loading");
    setGenerateError("");
    setCard(null);
    setAnswers({});
    setResult(null);
    setGradeError("");

    async function generate() {
      try {
        const newCard = await getOrCreateQuizGenerationRequest({
          workspaceId,
          trailId,
          conceptId,
          mode,
          forceNew: mode === "level_up" && retryTrigger > 0,
          retryTrigger,
        });
        if (cancelled) return;
        const initialAnswers: Record<string, string> = {};
        for (const q of newCard.questions) {
          initialAnswers[q.id] = "";
        }
        setCard(newCard);
        setAnswers(initialAnswers);
        setQuizState("answering");
      } catch (exc) {
        if (cancelled) return;
        setGenerateError(exc instanceof Error ? exc.message : "Could not generate quiz");
      }
    }

    void generate();
    return () => {
      cancelled = true;
    };
  }, [conceptId, mode, retryTrigger, workspaceId, trailId]);

  function handleRetry() {
    if (mode === "level_up") {
      // Generate a fresh quiz to prevent answer memorisation.
      setRetryTrigger((prev) => prev + 1);
    } else {
      // Practice: reuse the same card, just reset answers back to blank.
      if (card) {
        const resetAnswers: Record<string, string> = {};
        for (const q of card.questions) {
          resetAnswers[q.id] = "";
        }
        setAnswers(resetAnswers);
      }
      setResult(null);
      setGradeError("");
      setQuizState("answering");
    }
  }

  async function handleSubmit() {
    if (!card) {
      return;
    }
    setQuizState("grading");
    setGradeError("");

    const quizAnswers: QuizAnswer[] = card.questions.map((q) => ({
      question_id: q.id,
      answer: answers[q.id] ?? "",
    }));

    try {
      const gradeResult =
        mode === "level_up"
          ? await gradeLevelUpQuiz(workspaceId, trailId, conceptId, card.questions, quizAnswers)
          : await gradePracticeQuiz(workspaceId, trailId, conceptId, card.questions, quizAnswers);
      setResult(gradeResult);
      setQuizState("result");
      if (mode === "level_up") {
        onMasteryUpdated?.(conceptId, { status: gradeResult.mastery_status, score: gradeResult.score });
      }
    } catch (exc) {
      setGradeError(exc instanceof Error ? exc.message : "Could not grade quiz");
      setQuizState("answering");
    }
  }

  const allAnswered =
    card !== null && card.questions.every((q) => (answers[q.id] ?? "").trim().length > 0);

  if (quizState === "loading" && !generateError) {
    return (
      <div className="py-8 text-center text-sm text-slate-500">Generating quiz...</div>
    );
  }

  if (generateError) {
    return (
      <div className="space-y-4">
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {generateError}
        </div>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={handleRetry}
            className="rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Retry
          </button>
          <button
            type="button"
            onClick={onBack}
            className="text-sm text-slate-500 hover:text-slate-800"
          >
            Back
          </button>
        </div>
      </div>
    );
  }

  if (quizState === "result" && result) {
    const questionByid = Object.fromEntries((card?.questions ?? []).map((q) => [q.id, q]));
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span
            className={`rounded-full border px-3 py-1 text-sm font-semibold ${
              result.passed
                ? "border-green-200 bg-green-100 text-green-800"
                : "border-red-200 bg-red-100 text-red-800"
            }`}
          >
            {result.passed ? "Passed" : "Failed"}
          </span>
          <span className="text-sm font-medium text-slate-700">
            Score: {Math.round(result.score * 100)}%
          </span>
        </div>
        {result.per_question && result.per_question.length > 0 ? (
          <ol className="space-y-3">
            {result.per_question.map((item) => {
              const question = questionByid[item.question_id];
              return (
                <li
                  key={item.question_id}
                  className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm"
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="font-medium text-slate-800">
                      {question?.mastery_label ?? item.question_id}
                    </span>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${
                        item.score >= 0.7
                          ? "border-green-200 bg-green-50 text-green-700"
                          : "border-amber-200 bg-amber-50 text-amber-700"
                      }`}
                    >
                      {Math.round(item.score * 100)}%
                    </span>
                  </div>
                  <p className="text-slate-600">{item.feedback}</p>
                </li>
              );
            })}
          </ol>
        ) : null}
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
          {result.feedback}
        </div>
        {mode === "level_up" ? (
          <p className="text-xs text-slate-500">
            Status: {result.mastery_status.replace("_", " ")}
          </p>
        ) : null}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={handleRetry}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Retry
          </button>
          <button
            type="button"
            onClick={onBack}
            className="rounded-md border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">
          {mode === "level_up" ? "Level-Up Quiz" : "Practice Quiz"}
        </h3>
        <button
          type="button"
          onClick={onBack}
          className="text-xs text-slate-500 hover:text-slate-800"
        >
          Back
        </button>
      </div>
      {gradeError ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {gradeError}
        </div>
      ) : null}
      <ol className="space-y-5">
        {card?.questions.map((question, index) => (
          <li key={question.id} className="space-y-2">
            <p className="text-sm font-medium text-slate-800">
              {index + 1}. {question.prompt}
            </p>
            <p className="text-xs uppercase tracking-wide text-slate-500">
              {formatQuestionType(question.type)} · {question.difficulty ?? "standard"}
            </p>
            {question.type === "multiple_choice" ? (
              <div className="space-y-2" role="radiogroup" aria-label={`Answer to question ${index + 1}`}>
                {(question.options ?? []).map((option) => (
                  <label
                    key={option}
                    className="flex cursor-pointer items-start gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
                  >
                    <input
                      type="radio"
                      name={`question-${question.id}`}
                      value={option}
                      checked={(answers[question.id] ?? "") === option}
                      onChange={(event) =>
                        setAnswers((current) => ({
                          ...current,
                          [question.id]: event.target.value,
                        }))
                      }
                      disabled={quizState === "grading"}
                      className="mt-1"
                    />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            ) : question.type === "short_answer" ? (
              <input
                aria-label={`Answer to question ${index + 1}`}
                value={answers[question.id] ?? ""}
                onChange={(event) =>
                  setAnswers((current) => ({
                    ...current,
                    [question.id]: event.target.value,
                  }))
                }
                placeholder="Type a short answer..."
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 disabled:bg-slate-50"
                disabled={quizState === "grading"}
              />
            ) : (
              <textarea
                aria-label={`Answer to question ${index + 1}`}
                value={answers[question.id] ?? ""}
                onChange={(event) =>
                  setAnswers((current) => ({
                    ...current,
                    [question.id]: event.target.value,
                  }))
                }
                placeholder="Type your answer..."
                rows={4}
                className="w-full resize-none rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 disabled:bg-slate-50"
                disabled={quizState === "grading"}
              />
            )}
          </li>
        ))}
      </ol>
      <button
        type="button"
        onClick={() => void handleSubmit()}
        disabled={!allAnswered || quizState === "grading"}
        className="h-10 w-full rounded-md bg-blue-600 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {quizState === "grading" ? "Grading..." : "Submit"}
      </button>
    </div>
  );
}

function getOrCreateQuizGenerationRequest({
  workspaceId,
  trailId,
  conceptId,
  mode,
  forceNew,
  retryTrigger,
}: {
  workspaceId: string;
  trailId: string;
  conceptId: string;
  mode: "level_up" | "practice";
  forceNew: boolean;
  retryTrigger: number;
}): Promise<LevelUpCard> {
  const key = [workspaceId, trailId, conceptId, mode, forceNew ? `fresh-${retryTrigger}` : "reuse"].join(":");
  const existing = quizGenerationRequests.get(key);
  if (existing) {
    return existing;
  }

  const request = (
    mode === "level_up"
      ? generateLevelUpQuiz(workspaceId, trailId, conceptId, { force_new: forceNew })
      : generatePracticeQuiz(workspaceId, trailId, conceptId)
  ).finally(() => {
    if (quizGenerationRequests.get(key) === request) {
      quizGenerationRequests.delete(key);
    }
  });
  quizGenerationRequests.set(key, request);
  return request;
}

function formatQuestionType(type: LevelUpCard["questions"][number]["type"]): string {
  switch (type) {
    case "multiple_choice":
      return "multiple choice";
    case "short_answer":
      return "short answer";
    case "long_answer":
      return "long answer";
  }
}
