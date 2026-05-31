"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ArtifactRenderer } from "@/components/artifacts/ArtifactRenderer";
import { PinToggle } from "@/components/PinToggle";
import { QuizAttemptList } from "@/app/(app)/trails/[id]/components/quizShared";
import { listPins, listTrails, unpinItem } from "@/lib/api";
import type { ConceptPinItem } from "@/lib/api";
import type { ArtifactRead } from "@/lib/artifacts";
import type { FlashcardDeck, QuizAttempt, Trail } from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";

interface TrailPins {
  trail: Trail;
  artifacts: ArtifactRead[];
  quizAttempts: QuizAttempt[];
  flashcards: FlashcardDeck[];
  concepts: ConceptPinItem[];
}

export default function BookmarksPage() {
  const [workspaceId, setWorkspaceId] = useState("");
  const [groups, setGroups] = useState<TrailPins[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const id = await ensureWorkspaceId();
        // Bounded traversal: only the workspace's own Trails are visited, and
        // exactly one pins request is issued per Trail (no recursion / fan-out).
        const { trails } = await listTrails(id);
        const results = await Promise.all(
          trails.map(async (trail) => {
            try {
              const pins = await listPins(trail.workspace_id, trail.id);
              return {
                trail,
                artifacts: pins.artifacts,
                quizAttempts: pins.quiz_attempts,
                flashcards: pins.flashcards ?? [],
                concepts: pins.concepts ?? [],
              } satisfies TrailPins;
            } catch {
              return null;
            }
          }),
        );
        if (cancelled) {
          return;
        }
        setWorkspaceId(id);
        setGroups(
          results.filter(
            (group): group is TrailPins =>
              group !== null &&
              (group.artifacts.length > 0 ||
                group.quizAttempts.length > 0 ||
                group.flashcards.length > 0 ||
                group.concepts.length > 0),
          ),
        );
        setLoading(false);
      } catch (exc) {
        if (cancelled) {
          return;
        }
        setError(
          exc instanceof Error ? exc.message : "Could not load saved items",
        );
        setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  function dropArtifact(trailId: string, artifactId: string) {
    setGroups((current) =>
      prune(
        current.map((group) =>
          group.trail.id === trailId
            ? {
                ...group,
                artifacts: group.artifacts.filter((a) => a.id !== artifactId),
              }
            : group,
        ),
      ),
    );
  }

  function dropAttempt(trailId: string, attemptId: string) {
    setGroups((current) =>
      prune(
        current.map((group) =>
          group.trail.id === trailId
            ? {
                ...group,
                quizAttempts: group.quizAttempts.filter(
                  (a) => a.id !== attemptId,
                ),
              }
            : group,
        ),
      ),
    );
  }

  function dropFlashcard(trailId: string, deckId: string) {
    setGroups((current) =>
      prune(
        current.map((group) =>
          group.trail.id === trailId
            ? {
                ...group,
                flashcards: group.flashcards.filter((d) => d.id !== deckId),
              }
            : group,
        ),
      ),
    );
  }

  async function handleUnpinConcept(conceptId: string, trailId: string) {
    if (!workspaceId) return;
    await unpinItem(workspaceId, trailId, "concept", conceptId);
    setGroups((current) =>
      prune(
        current.map((group) =>
          group.trail.id === trailId
            ? {
                ...group,
                concepts: group.concepts.filter(
                  (c) => c.concept_id !== conceptId,
                ),
              }
            : group,
        ),
      ),
    );
  }

  return (
    <div className="w-full space-y-6 px-4 py-8">
      <header className="space-y-1 border-b border-slate-200 pb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Saved</h1>
        <p className="text-sm leading-6 text-slate-500">
          Artifacts, quiz attempts, and flashcard decks you&apos;ve pinned, grouped by Trail.
        </p>
      </header>

      {loading ? (
        <p className="py-8 text-center text-sm text-slate-500">
          Loading saved items...
        </p>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      ) : groups.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          Nothing saved yet. Use the Save button on an artifact or a quiz
          attempt inside a Trail to pin it here.
        </p>
      ) : (
        <div className="space-y-8">
          {groups.map((group) => (
            <section key={group.trail.id} className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-900">
                  {group.trail.title}
                </h2>
                <Link
                  href={`/trails/${group.trail.id}`}
                  className="text-xs text-blue-600 hover:underline"
                >
                  Open Trail
                </Link>
              </div>

              {group.artifacts.length > 0 ? (
                <div className="grid gap-3">
                  {group.artifacts.map((artifact) => (
                    <div key={artifact.id} className="space-y-2">
                      <div className="flex justify-end">
                        <PinToggle
                          workspaceId={workspaceId}
                          trailId={group.trail.id}
                          itemType="artifact"
                          itemId={artifact.id}
                          initialPinned
                          onChange={(pinned) => {
                            if (!pinned) {
                              dropArtifact(group.trail.id, artifact.id);
                            }
                          }}
                        />
                      </div>
                      <ArtifactRenderer envelope={artifact.payload} />
                    </div>
                  ))}
                </div>
              ) : null}

              {group.quizAttempts.length > 0 ? (
                <QuizAttemptList
                  attempts={group.quizAttempts}
                  pinContext={{
                    workspaceId,
                    trailId: group.trail.id,
                    pinned: true,
                  }}
                  onUnpin={(attemptId) =>
                    dropAttempt(group.trail.id, attemptId)
                  }
                />
              ) : null}

              {group.flashcards.length > 0 ? (
                <div className="grid gap-3">
                  {group.flashcards.map((deck) => (
                    <div
                      key={deck.id}
                      className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 shadow-sm"
                    >
                      <div className="space-y-0.5">
                        <p className="text-sm font-medium text-slate-900">
                          {deck.title}
                        </p>
                        <p className="text-xs text-slate-500">
                          {deck.cards.length}{" "}
                          {deck.cards.length === 1 ? "card" : "cards"}
                        </p>
                      </div>
                      <PinToggle
                        workspaceId={workspaceId}
                        trailId={group.trail.id}
                        itemType="flashcard"
                        itemId={deck.id}
                        initialPinned
                        onChange={(pinned) => {
                          if (!pinned) {
                            dropFlashcard(group.trail.id, deck.id);
                          }
                        }}
                      />
                    </div>
                  ))}
                </div>
              ) : null}

              {group.concepts.length > 0 ? (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {group.concepts.map((c) => (
                    <div
                      key={c.concept_id}
                      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm flex items-start justify-between gap-3"
                    >
                      <div className="min-w-0">
                        <p className="font-medium truncate">{c.concept_title}</p>
                        <p className="text-sm text-muted-foreground truncate">
                          {c.trail_title}
                        </p>
                      </div>
                      <div className="flex gap-2 shrink-0">
                        <a
                          href={`/trails/${c.trail_id}`}
                          className="inline-flex items-center rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                        >
                          Go to trail
                        </a>
                        <button
                          type="button"
                          className="inline-flex items-center rounded-md px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100"
                          onClick={() =>
                            handleUnpinConcept(c.concept_id, c.trail_id)
                          }
                        >
                          Unpin
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function prune(groups: TrailPins[]): TrailPins[] {
  return groups.filter(
    (group) =>
      group.artifacts.length > 0 ||
      group.quizAttempts.length > 0 ||
      group.flashcards.length > 0 ||
      group.concepts.length > 0,
  );
}
