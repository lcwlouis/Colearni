import { describe, expect, it } from "vitest";
import { buildUploadQueueSeeds, uploadQueueReducer } from "./upload-queue";

describe("uploadQueueReducer", () => {
  it("enqueues files as queued items", () => {
    const state = uploadQueueReducer([], {
      type: "enqueue",
      items: [
        { localId: "a", fileName: "a.md" },
        { localId: "b", fileName: "b.pdf" },
      ],
    });
    expect(state).toEqual([
      {
        localId: "a",
        fileName: "a.md",
        phase: "queued",
        chunkCount: null,
        error: null,
      },
      {
        localId: "b",
        fileName: "b.pdf",
        phase: "queued",
        chunkCount: null,
        error: null,
      },
    ]);
  });

  it("updates item phases through upload lifecycle", () => {
    let state = uploadQueueReducer([], {
      type: "enqueue",
      items: [{ localId: "x", fileName: "notes.txt" }],
    });
    state = uploadQueueReducer(state, { type: "mark_uploading", localId: "x" });
    expect(state[0]?.phase).toBe("uploading");

    state = uploadQueueReducer(state, {
      type: "mark_uploaded",
      localId: "x",
      chunkCount: 3,
    });
    expect(state[0]).toMatchObject({
      phase: "uploaded",
      chunkCount: 3,
      error: null,
    });
  });

  it("records upload failures", () => {
    let state = uploadQueueReducer([], {
      type: "enqueue",
      items: [{ localId: "x", fileName: "broken.pdf" }],
    });
    state = uploadQueueReducer(state, {
      type: "mark_failed",
      localId: "x",
      error: "500",
    });
    expect(state[0]).toMatchObject({
      phase: "failed",
      error: "500",
    });
  });
});

describe("buildUploadQueueSeeds", () => {
  it("builds deterministic seed ids from file metadata", () => {
    const seeds = buildUploadQueueSeeds(
      [
        { name: "a.md", size: 10, lastModified: 100 },
        { name: "b.md", size: 20, lastModified: 200 },
      ],
      "batch-1",
    );
    expect(seeds).toEqual([
      { localId: "batch-1-0-a.md-10-100", fileName: "a.md" },
      { localId: "batch-1-1-b.md-20-200", fileName: "b.md" },
    ]);
  });
});

