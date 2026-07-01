import { vi, describe, it, expect, beforeEach } from "vitest";

// Mock only the HTTP client; keep the real unwrap() so ApiError is thrown for real.
// vi.hoisted so `post` exists when the hoisted vi.mock factory runs.
const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, api: { POST: post } };
});

import { previewWithAutoSeed } from "./api";
import type { SceneDocument } from "@/api/types";

const doc: SceneDocument = { grid: [], render: {} };
const ok = (chars: number[][]) => ({
  data: { rows: chars.length, cols: chars[0]?.length ?? 0, characters: chars },
  response: { ok: true, status: 200 },
});
const missing = (key: string) => ({
  error: { detail: `cannot render scene: '${key}'` },
  response: { ok: false, status: 422 },
});

beforeEach(() => post.mockReset());

describe("previewWithAutoSeed", () => {
  it("seeds each missing key the server reports, then returns the render", async () => {
    post
      .mockResolvedValueOnce(missing("badge_color"))
      .mockResolvedValueOnce(missing("time_color"))
      .mockResolvedValueOnce(ok([[0, 0]]));

    const out = await previewWithAutoSeed(doc, {});
    expect(out.rows).toBe(1);
    expect(post).toHaveBeenCalledTimes(3);
    // final attempt carries both seeded keys defaulted to white (69)
    const lastBody = post.mock.calls[2][1].body;
    expect(lastBody.sample_data).toMatchObject({ badge_color: 69, time_color: 69 });
  });

  it("rethrows a non-seedable 422 (real document error)", async () => {
    post.mockResolvedValue({
      error: { detail: "invalid scene document: row 0 must be 22 wide" },
      response: { ok: false, status: 422 },
    });
    await expect(previewWithAutoSeed(doc, {})).rejects.toThrow(/22 wide/);
    expect(post).toHaveBeenCalledTimes(1);
  });
});
