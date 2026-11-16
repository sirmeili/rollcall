import { describe, expect, it } from "vitest";
import type { SyncStatus } from "#lib/api/catalog.ts";
import { attemptNote, failureText, refreshText, versionText } from "#lib/catalog-sync.ts";

const NEVER: SyncStatus = {
  last_success_at: null,
  last_attempt_at: null,
  last_result: null,
  last_reason: null,
  dataset_version: null,
  colors: 0,
};

describe("Catalog sync words", () => {
  it("shows a version with a v, or a dash before the first sync", () => {
    expect(versionText("2026.11.15")).toBe("v2026.11.15");
    expect(versionText(null)).toBe("—");
  });

  it("has no note and no warning before any attempt", () => {
    expect(attemptNote(NEVER)).toBe("");
    expect(failureText(NEVER)).toBeNull();
  });

  it("still says a sync failed when no reason came with it", () => {
    const failed: SyncStatus = { ...NEVER, last_result: "failed" };

    expect(attemptNote(failed)).toBe("Failed: unknown error");
    expect(failureText(failed)).toBe("Last attempt failed: unknown error. There is no copy yet.");
    expect(refreshText(null, failed)).toBe("Sync failed: unknown error.");
  });

  it("says up to date without a date when there was no earlier success", () => {
    expect(refreshText(null, { ...NEVER, last_result: "not_modified" })).toBe("Up to date.");
  });
});
