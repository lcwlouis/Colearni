/**
 * U3: Visible phase policy tests.
 *
 * Verifies that the user-facing phase labels match the U1 policy:
 * - pre-output phases (thinking, searching, finalizing) → "Thinking…"
 * - visible text arriving (responding) → "Generating response…"
 * - idle → ""
 */

import { describe, expect, it } from "vitest";
import { ACTIVITY_LABELS, PHASE_LABELS, visiblePhaseLabel } from "./types";
import type { ChatPhase } from "./types";
import type { TutorActivity } from "@/lib/api/types";

describe("visiblePhaseLabel (U1 policy)", () => {
  it("shows Thinking… for thinking phase", () => {
    expect(visiblePhaseLabel("thinking")).toBe("Thinking…");
  });

  it("shows Thinking… for searching phase (not Searching knowledge base…)", () => {
    expect(visiblePhaseLabel("searching")).toBe("Thinking…");
  });

  it("shows Thinking… for finalizing phase (not Finalizing…)", () => {
    expect(visiblePhaseLabel("finalizing")).toBe("Thinking…");
  });

  it("shows Generating response… for responding phase", () => {
    expect(visiblePhaseLabel("responding")).toBe("Generating response…");
  });

  it("shows empty string for idle phase", () => {
    expect(visiblePhaseLabel("idle")).toBe("");
  });

  it("all pre-output phases map to the same label", () => {
    const preOutputPhases: ChatPhase[] = ["thinking", "searching", "finalizing"];
    const labels = preOutputPhases.map(visiblePhaseLabel);
    expect(new Set(labels).size).toBe(1);
    expect(labels[0]).toBe("Thinking…");
  });

  it("PHASE_LABELS never contains Searching knowledge base…", () => {
    const values = Object.values(PHASE_LABELS);
    expect(values).not.toContain("Searching knowledge base…");
  });

  it("PHASE_LABELS never contains Finalizing…", () => {
    const values = Object.values(PHASE_LABELS);
    expect(values).not.toContain("Finalizing…");
  });
});

describe("ACTIVITY_LABELS (AR3.3)", () => {
  it("covers all 8 activity types", () => {
    const keys = Object.keys(ACTIVITY_LABELS);
    expect(keys).toHaveLength(8);
    expect(keys).toContain("planning_turn");
    expect(keys).toContain("retrieving_chunks");
    expect(keys).toContain("expanding_graph");
    expect(keys).toContain("checking_mastery");
    expect(keys).toContain("preparing_quiz");
    expect(keys).toContain("grading_quiz");
    expect(keys).toContain("verifying_citations");
    expect(keys).toContain("generating_reply");
  });

  it("all labels are non-empty strings", () => {
    for (const label of Object.values(ACTIVITY_LABELS)) {
      expect(typeof label).toBe("string");
      expect(label.length).toBeGreaterThan(0);
    }
  });

  it("activity labels are human-readable (no underscores)", () => {
    for (const label of Object.values(ACTIVITY_LABELS)) {
      expect(label).not.toMatch(/_/);
    }
  });
});
