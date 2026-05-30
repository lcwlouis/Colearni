"use client";

import { useEffect, useState, type KeyboardEvent } from "react";

import {
  generateLevelUpQuiz,
  generatePracticeQuiz,
  gradeLevelUpQuiz,
  gradePracticeQuiz,
} from "@/lib/api";
import type {
  GradeResult,
  LevelUpCard,
  MasteryStatus,
  QuizAnswer,
  QuizQuestion,
} from "@/lib/types";

import { QuizMarkdown } from "./QuizMarkdown";
import {
  FormattedFeedback,
  displayOverallFeedback,
  formatMasteryStatus,
  formatQuestionType,
  humanizeLabel,
  questionScoreBand,
} from "./quizShared";

type QuizState = "loading" | "answering" | "grading" | "result";

type QuizPanelState = {
  key: string;
  quizState: QuizState;
  card: LevelUpCard | null;
  answers: Record<string, string>;
  result: GradeResult | null;
  generateError: string;
  gradeError: string;
};

function loadingQuizPanelState(key: string): QuizPanelState {
  return {
    key,
    quizState: "loading",
    card: null,
    answers: {},
    result: null,
    generateError: "",
    gradeError: "",
  };
}

function initialQuizAnswers(card: LevelUpCard): Record<string, string> {
  return Object.fromEntries(
    card.questions.map((q) => [
      q.id,
      // Ordering starts from the presented order so the learner reorders it.
      q.type === "ordering" ? (q.options ?? []).join("\n") : "",
    ]),
  );
}

const quizGenerationRequests = new Map<string, Promise<LevelUpCard>>();

interface QuizPanelProps {
  workspaceId: string;
  trailId: string;
  conceptId: string;
  mode: "level_up" | "practice";
  onBack: () => void;
  onViewHistory?: () => void;
  onMasteryUpdated?: (
    conceptId: string,
    update: { status: MasteryStatus; score: number },
  ) => void;
}

export function QuizPanel({
  workspaceId,
  trailId,
  conceptId,
  mode,
  onBack,
  onViewHistory,
  onMasteryUpdated,
}: QuizPanelProps) {
  const [retryTrigger, setRetryTrigger] = useState(0);
  const quizKey = [workspaceId, trailId, conceptId, mode, retryTrigger].join(
    ":",
  );
  const [quizData, setQuizData] = useState<QuizPanelState>(() =>
    loadingQuizPanelState(quizKey),
  );
  const currentQuizData =
    quizData.key === quizKey ? quizData : loadingQuizPanelState(quizKey);
  const { quizState, card, answers, result, generateError, gradeError } =
    currentQuizData;

  useEffect(() => {
    let cancelled = false;

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
        setQuizData({
          key: quizKey,
          quizState: "answering",
          card: newCard,
          answers: initialQuizAnswers(newCard),
          result: null,
          generateError: "",
          gradeError: "",
        });
      } catch (exc) {
        if (cancelled) return;
        setQuizData({
          ...loadingQuizPanelState(quizKey),
          generateError:
            exc instanceof Error ? exc.message : "Could not generate quiz",
        });
      }
    }

    void generate();
    return () => {
      cancelled = true;
    };
  }, [conceptId, mode, retryTrigger, workspaceId, trailId, quizKey]);

  function handleRetry() {
    if (mode === "level_up") {
      // Generate a fresh quiz to prevent answer memorisation.
      setRetryTrigger((prev) => prev + 1);
    } else {
      // Practice: reuse the same card, just reset answers back to blank.
      setQuizData((current) => {
        if (current.key !== quizKey) {
          return current;
        }
        return {
          ...current,
          answers: current.card
            ? initialQuizAnswers(current.card)
            : current.answers,
          result: null,
          gradeError: "",
          quizState: "answering",
        };
      });
    }
  }

  async function handleSubmit() {
    if (!card) {
      return;
    }
    setQuizData((current) =>
      current.key === quizKey
        ? { ...current, quizState: "grading", gradeError: "" }
        : current,
    );

    const quizAnswers: QuizAnswer[] = card.questions.map((q) => ({
      question_id: q.id,
      answer: answers[q.id] ?? "",
    }));

    try {
      const gradeResult =
        mode === "level_up"
          ? await gradeLevelUpQuiz(
              workspaceId,
              trailId,
              conceptId,
              card.questions,
              quizAnswers,
            )
          : await gradePracticeQuiz(
              workspaceId,
              trailId,
              conceptId,
              card.questions,
              quizAnswers,
            );
      setQuizData((current) =>
        current.key === quizKey
          ? { ...current, result: gradeResult, quizState: "result" }
          : current,
      );
      if (mode === "level_up") {
        onMasteryUpdated?.(conceptId, {
          status: gradeResult.mastery_status,
          score: gradeResult.score,
        });
      }
    } catch (exc) {
      setQuizData((current) =>
        current.key === quizKey
          ? {
              ...current,
              gradeError:
                exc instanceof Error ? exc.message : "Could not grade quiz",
              quizState: "answering",
            }
          : current,
      );
    }
  }

  function handleAnswerChange(questionId: string, answer: string) {
    setQuizData((current) =>
      current.key === quizKey
        ? {
            ...current,
            answers: { ...current.answers, [questionId]: answer },
          }
        : current,
    );
  }

  function handleCodeKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
    questionId: string,
    value: string,
  ) {
    // Tab indents instead of moving focus, so code answers stay usable.
    if (event.key !== "Tab") {
      return;
    }
    event.preventDefault();
    const target = event.currentTarget;
    const start = target.selectionStart;
    const end = target.selectionEnd;
    const next = `${value.slice(0, start)}  ${value.slice(end)}`;
    handleAnswerChange(questionId, next);
    requestAnimationFrame(() => {
      target.selectionStart = start + 2;
      target.selectionEnd = start + 2;
    });
  }

  function toggleMultiSelect(question: QuizQuestion, option: string) {
    const selected = new Set(
      (answers[question.id] ?? "").split("\n").filter(Boolean),
    );
    if (selected.has(option)) {
      selected.delete(option);
    } else {
      selected.add(option);
    }
    // Preserve the option order for a stable serialization.
    const ordered = (question.options ?? []).filter((o) => selected.has(o));
    handleAnswerChange(question.id, ordered.join("\n"));
  }

  function moveOrderingItem(
    question: QuizQuestion,
    index: number,
    direction: -1 | 1,
  ) {
    const items = orderingItems(answers[question.id] ?? "", question);
    const target = index + direction;
    if (target < 0 || target >= items.length) {
      return;
    }
    [items[index], items[target]] = [items[target], items[index]];
    handleAnswerChange(question.id, items.join("\n"));
  }

  function setClozeBlank(
    question: QuizQuestion,
    blankIndex: number,
    value: string,
  ) {
    const blanks = countBlanks(question.prompt);
    const parts = clozeValues(answers[question.id] ?? "", blanks);
    parts[blankIndex] = value;
    handleAnswerChange(question.id, parts.join("\n"));
  }

  const allAnswered =
    card !== null &&
    card.questions.every((q) => isAnswered(q, answers[q.id] ?? ""));

  if (quizState === "loading" && !generateError) {
    return (
      <div className="space-y-4">
        <QuizProgressCard mode={mode} phase="generating" />
        {onViewHistory ? <ViewHistoryButton onClick={onViewHistory} /> : null}
      </div>
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
    const questionById = Object.fromEntries(
      (card?.questions ?? []).map((q) => [q.id, q]),
    );
    return (
      <div className="space-y-5">
        <section
          className={`rounded-xl border p-4 ${
            result.passed
              ? "border-green-200 bg-green-50"
              : "border-amber-200 bg-amber-50"
          }`}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {mode === "level_up" ? "Level-up result" : "Practice result"}
              </p>
              <h3 className="mt-1 text-lg font-semibold text-slate-950">
                {result.passed ? "Mastery confirmed" : "Review recommended"}
              </h3>
              {mode === "level_up" ? (
                <p className="mt-1 text-sm text-slate-600">
                  Status: {formatMasteryStatus(result.mastery_status)}
                </p>
              ) : null}
            </div>
            <div className="rounded-lg bg-white px-3 py-2 text-right shadow-sm ring-1 ring-slate-200">
              <p className="text-xs uppercase tracking-wide text-slate-500">
                Score
              </p>
              <p className="text-xl font-semibold text-slate-950">
                {Math.round(result.score * 100)}%
              </p>
              <p className="sr-only">
                Score: {Math.round(result.score * 100)}%
              </p>
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h4 className="text-sm font-semibold text-slate-900">
            Overall feedback
          </h4>
          <FormattedFeedback text={displayOverallFeedback(result.feedback)} />
        </section>

        {result.per_question && result.per_question.length > 0 ? (
          <section className="space-y-3">
            <h4 className="text-sm font-semibold text-slate-900">
              Question review
            </h4>
            <ol className="space-y-3">
              {result.per_question.map((item, index) => {
                const question = questionById[item.question_id];
                const band = questionScoreBand(item.score);
                return (
                  <li
                    key={item.question_id}
                    className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm"
                  >
                    <div className="mb-2 flex items-start justify-between gap-3">
                      <div>
                        <div className="font-medium text-slate-900">
                          <span className="mr-1">{index + 1}.</span>
                          {question?.prompt ? (
                            <QuizMarkdown
                              text={question.prompt}
                              className="inline-block align-top"
                            />
                          ) : (
                            item.question_id
                          )}
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                          {question?.mastery_label
                            ? humanizeLabel(question.mastery_label)
                            : "Question feedback"}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold ${band.className}`}
                      >
                        {band.label} · {Math.round(item.score * 100)}%
                      </span>
                    </div>
                    <FormattedFeedback text={item.feedback} compact />
                  </li>
                );
              })}
            </ol>
          </section>
        ) : null}

        <div className="flex flex-wrap items-center gap-3">
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
          {onViewHistory ? (
            <button
              type="button"
              onClick={onViewHistory}
              className="text-sm text-blue-700 hover:text-blue-900"
            >
              View past attempts
            </button>
          ) : null}
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
      {quizState === "grading" ? (
        <QuizProgressCard mode={mode} phase="grading" />
      ) : null}
      {gradeError ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {gradeError}
        </div>
      ) : null}
      <ol className="space-y-5">
        {card?.questions.map((question, index) => (
          <li key={question.id} className="space-y-2">
            <div className="text-sm font-medium text-slate-800">
              <span className="mr-1">{index + 1}.</span>
              <QuizMarkdown
                text={question.prompt}
                className="inline-block align-top"
              />
            </div>
            <p className="text-xs uppercase tracking-wide text-slate-500">
              {formatQuestionType(question.type)} ·{" "}
              {question.difficulty ?? "standard"}
            </p>
            <QuestionInput
              question={question}
              value={answers[question.id] ?? ""}
              disabled={quizState === "grading"}
              index={index}
              onChange={(value) => handleAnswerChange(question.id, value)}
              onToggleMultiSelect={(option) =>
                toggleMultiSelect(question, option)
              }
              onMoveOrdering={(i, dir) => moveOrderingItem(question, i, dir)}
              onSetCloze={(i, value) => setClozeBlank(question, i, value)}
              onCodeKeyDown={(event) =>
                handleCodeKeyDown(
                  event,
                  question.id,
                  answers[question.id] ?? "",
                )
              }
            />
          </li>
        ))}
      </ol>
      <button
        type="button"
        onClick={() => void handleSubmit()}
        disabled={!allAnswered || quizState === "grading"}
        className="h-10 w-full rounded-md bg-blue-600 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {quizState === "grading" ? "Reviewing answers..." : "Submit"}
      </button>
      {onViewHistory ? <ViewHistoryButton onClick={onViewHistory} /> : null}
    </div>
  );
}

function QuestionInput({
  question,
  value,
  disabled,
  index,
  onChange,
  onToggleMultiSelect,
  onMoveOrdering,
  onSetCloze,
  onCodeKeyDown,
}: {
  question: QuizQuestion;
  value: string;
  disabled: boolean;
  index: number;
  onChange: (value: string) => void;
  onToggleMultiSelect: (option: string) => void;
  onMoveOrdering: (index: number, direction: -1 | 1) => void;
  onSetCloze: (blankIndex: number, value: string) => void;
  onCodeKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
}) {
  const label = `Answer to question ${index + 1}`;

  if (question.type === "multiple_choice") {
    return (
      <div className="space-y-2" role="radiogroup" aria-label={label}>
        {(question.options ?? []).map((option) => (
          <label
            key={option}
            className="flex cursor-pointer items-start gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
          >
            <input
              type="radio"
              name={`question-${question.id}`}
              value={option}
              checked={value === option}
              onChange={(event) => onChange(event.target.value)}
              disabled={disabled}
              className="mt-1"
            />
            <span>{option}</span>
          </label>
        ))}
      </div>
    );
  }

  if (question.type === "multi_select") {
    const selected = new Set(value.split("\n").filter(Boolean));
    return (
      <div className="space-y-2" role="group" aria-label={label}>
        <p className="text-xs text-slate-500">Select all that apply.</p>
        {(question.options ?? []).map((option) => (
          <label
            key={option}
            className="flex cursor-pointer items-start gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
          >
            <input
              type="checkbox"
              checked={selected.has(option)}
              onChange={() => onToggleMultiSelect(option)}
              disabled={disabled}
              className="mt-1"
            />
            <span>{option}</span>
          </label>
        ))}
      </div>
    );
  }

  if (question.type === "ordering") {
    const items = orderingItems(value, question);
    return (
      <div className="space-y-2" aria-label={label}>
        <p className="text-xs text-slate-500">
          Use the arrows to arrange these in the correct order.
        </p>
        <ol className="space-y-2">
          {items.map((item, i) => (
            <li
              key={item}
              className="flex items-center justify-between gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
            >
              <span>
                <span className="mr-2 text-slate-400">{i + 1}.</span>
                {item}
              </span>
              <span className="flex shrink-0 gap-1">
                <button
                  type="button"
                  aria-label={`Move "${item}" up`}
                  onClick={() => onMoveOrdering(i, -1)}
                  disabled={disabled || i === 0}
                  className="rounded border border-slate-200 px-2 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label={`Move "${item}" down`}
                  onClick={() => onMoveOrdering(i, 1)}
                  disabled={disabled || i === items.length - 1}
                  className="rounded border border-slate-200 px-2 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                >
                  ↓
                </button>
              </span>
            </li>
          ))}
        </ol>
      </div>
    );
  }

  if (question.type === "cloze") {
    const blanks = countBlanks(question.prompt);
    const parts = clozeValues(value, blanks);
    return (
      <div className="space-y-2" aria-label={label}>
        {parts.map((part, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-16 shrink-0 text-xs uppercase tracking-wide text-slate-500">
              Blank {i + 1}
            </span>
            <input
              aria-label={`Blank ${i + 1} for question ${index + 1}`}
              value={part}
              onChange={(event) => onSetCloze(i, event.target.value)}
              placeholder="Fill in..."
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 disabled:bg-slate-50"
              disabled={disabled}
            />
          </div>
        ))}
      </div>
    );
  }

  if (question.type === "short_answer") {
    return (
      <input
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Type a short answer..."
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 disabled:bg-slate-50"
        disabled={disabled}
      />
    );
  }

  if (question.type === "code") {
    return (
      <textarea
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onCodeKeyDown}
        placeholder="Type your code or pseudocode... (Tab indents, Shift+Enter for a new line)"
        rows={8}
        spellCheck={false}
        wrap="off"
        className="w-full resize-y rounded-md border border-slate-300 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-100 outline-none focus:border-blue-500 disabled:opacity-60"
        disabled={disabled}
      />
    );
  }

  return (
    <textarea
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder="Type your answer..."
      rows={4}
      className="w-full resize-y rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 disabled:bg-slate-50"
      disabled={disabled}
    />
  );
}

function ViewHistoryButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-md border border-dashed border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
    >
      View past attempts
    </button>
  );
}

function QuizProgressCard({
  mode,
  phase,
}: {
  mode: "level_up" | "practice";
  phase: "generating" | "grading";
}) {
  const isGenerating = phase === "generating";
  const title = isGenerating
    ? mode === "level_up"
      ? "Preparing your level-up quiz..."
      : "Preparing practice questions..."
    : "Reviewing your answers...";
  const detail = isGenerating
    ? mode === "level_up"
      ? "Building a fresh mastery check from this concept's labels. If you already started one, we'll resume the saved draft."
      : "Creating low-stakes practice questions for review."
    : mode === "level_up"
      ? "Checking reasoning, saving feedback, and updating mastery."
      : "Checking reasoning and saving practice feedback.";

  return (
    <div
      className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 h-3 w-3 animate-pulse rounded-full bg-blue-500" />
        <div>
          <p className="font-semibold">{title}</p>
          <p className="mt-1 text-blue-800">{detail}</p>
          {isGenerating ? (
            <p className="mt-2 text-xs text-blue-700">
              Question text stays hidden until the quiz is ready.
            </p>
          ) : null}
        </div>
      </div>
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
  const key = [
    workspaceId,
    trailId,
    conceptId,
    mode,
    forceNew ? `fresh-${retryTrigger}` : "reuse",
  ].join(":");
  const existing = quizGenerationRequests.get(key);
  if (existing) {
    return existing;
  }

  const request = (
    mode === "level_up"
      ? generateLevelUpQuiz(workspaceId, trailId, conceptId, {
          force_new: forceNew,
        })
      : generatePracticeQuiz(workspaceId, trailId, conceptId)
  ).finally(() => {
    if (quizGenerationRequests.get(key) === request) {
      quizGenerationRequests.delete(key);
    }
  });
  quizGenerationRequests.set(key, request);
  return request;
}

function isAnswered(question: QuizQuestion, value: string): boolean {
  if (question.type === "multi_select") {
    return value.split("\n").filter(Boolean).length > 0;
  }
  if (question.type === "ordering") {
    return orderingItems(value, question).length > 0;
  }
  if (question.type === "cloze") {
    const blanks = countBlanks(question.prompt);
    const parts = clozeValues(value, blanks);
    return parts.length === blanks && parts.every((p) => p.trim().length > 0);
  }
  return value.trim().length > 0;
}

function orderingItems(value: string, question: QuizQuestion): string[] {
  const items = value.split("\n").filter(Boolean);
  return items.length > 0 ? items : (question.options ?? []);
}

function countBlanks(prompt: string): number {
  const matches = prompt.match(/_{4,}/g);
  return matches ? matches.length : 1;
}

function clozeValues(value: string, blanks: number): string[] {
  const parts = value ? value.split("\n") : [];
  while (parts.length < blanks) {
    parts.push("");
  }
  return parts.slice(0, blanks);
}
