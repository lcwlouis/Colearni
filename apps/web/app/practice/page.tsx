"use client";

import { useState } from "react";
import { AsyncState } from "@/components/async-state";
import { ApiError, apiClient } from "@/lib/api/client";

export default function PracticePage() {
  const [workspace_id, setWorkspace] = useState("1"), [user_id, setUser] = useState("1"), [concept_id, setConcept] = useState("1"), [question_count, setQuestionCount] = useState("5"), [card_count, setCardCount] = useState("6");
  const [loading, setLoading] = useState(false), [error, setError] = useState<string | null>(null), [data, setData] = useState<unknown | null>(null);

  async function run(action: "level_up" | "practice_quiz" | "flashcards") {
    setLoading(true); setError(null); setData(null);
    try {
      const shared = { workspace_id: Number(workspace_id), user_id: Number(user_id), concept_id: Number(concept_id) };
      setData(action === "level_up" ? await apiClient.createLevelUpQuiz({ ...shared, question_count: Number(question_count) }) : action === "practice_quiz" ? await apiClient.createPracticeQuiz({ ...shared, question_count: Math.max(3, Math.min(6, Number(question_count))) }) : await apiClient.generatePracticeFlashcards({ workspace_id: shared.workspace_id, concept_id: shared.concept_id, card_count: Number(card_count) }));
    } catch (err: unknown) { setError(err instanceof ApiError ? err.message : "Practice request failed"); }
    finally { setLoading(false); }
  }

  return (
    <section className="panel stack">
      <h1>Quizzes/practice entry points</h1>
      <p>Submit endpoints are in the typed client; this scaffold covers create/generate entry points.</p>
      <div className="grid two">
        <label className="field">
          <span className="field-label">Workspace ID</span>
          <input type="number" min={1} value={workspace_id} onChange={(e) => setWorkspace(e.target.value)} />
        </label>
        <label className="field">
          <span className="field-label">User ID</span>
          <input type="number" min={1} value={user_id} onChange={(e) => setUser(e.target.value)} />
        </label>
      </div>
      <div className="grid two">
        <label className="field">
          <span className="field-label">Concept ID</span>
          <input type="number" min={1} value={concept_id} onChange={(e) => setConcept(e.target.value)} />
        </label>
        <label className="field">
          <span className="field-label">Question count</span>
          <input
            type="number"
            min={3}
            max={10}
            value={question_count}
            onChange={(e) => setQuestionCount(e.target.value)}
          />
        </label>
      </div>
      <label className="field">
        <span className="field-label">Flashcard count</span>
        <input type="number" min={3} max={12} value={card_count} onChange={(e) => setCardCount(e.target.value)} />
      </label>
      <div className="button-row"><button type="button" disabled={loading} onClick={() => run("level_up")}>Create level-up quiz</button><button type="button" className="secondary" disabled={loading} onClick={() => run("practice_quiz")}>Create practice quiz</button><button type="button" className="secondary" disabled={loading} onClick={() => run("flashcards")}>Generate flashcards</button></div>
      <AsyncState loading={loading} error={error} empty={!data} emptyLabel="Choose one entry action." />
      {data ? <pre>{JSON.stringify(data, null, 2)}</pre> : null}
    </section>
  );
}
