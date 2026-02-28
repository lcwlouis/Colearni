/**
 * U3: Visible phase policy tests.
 *
 * Verifies that the user-facing phase labels match the U1 policy:
 * - pre-output phases (thinking, searching, finalizing) → "Thinking…"
 * - visible text arriving (responding) → "Generating response…"
 * - idle → ""
 */

import { describe, expect, it } from "vitest";
import { PHASE_LABELS, visiblePhaseLabel } from "./types";
import type { ChatPhase } from "./types";

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
