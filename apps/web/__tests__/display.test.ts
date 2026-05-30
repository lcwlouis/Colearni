import { describe, expect, test } from "vitest";

import {
  formatBloomLevel,
  formatGraphSize,
  titleCase,
} from "@/lib/display";

describe("display formatters", () => {
  test("titleCase handles single words, snake_case and kebab-case", () => {
    expect(titleCase("apply")).toBe("Apply");
    expect(titleCase("needs_review")).toBe("Needs Review");
    expect(titleCase("free-explore")).toBe("Free Explore");
    expect(titleCase("UNDERSTAND")).toBe("Understand");
  });

  test("formatBloomLevel title-cases each level", () => {
    expect(formatBloomLevel("remember")).toBe("Remember");
    expect(formatBloomLevel("understand")).toBe("Understand");
    expect(formatBloomLevel("create")).toBe("Create");
  });

  test("formatGraphSize builds the concept-count label", () => {
    expect(formatGraphSize(40)).toBe("Up to 40 concepts");
    expect(formatGraphSize(100)).toBe("Up to 100 concepts");
  });
});
