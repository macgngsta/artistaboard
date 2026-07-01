import { describe, it, expect } from "vitest";
import { formatAge, isStale } from "./freshness";

describe("formatAge", () => {
  it("reads 'never polled' when the series has no snapshot", () => {
    expect(formatAge({ has_data: false, age_seconds: null })).toBe("never polled");
    // has_data true but null age is still treated as never (defensive)
    expect(formatAge({ has_data: true, age_seconds: null })).toBe("never polled");
  });

  it("scales the unit with the age", () => {
    expect(formatAge({ has_data: true, age_seconds: 2 })).toBe("just now");
    expect(formatAge({ has_data: true, age_seconds: 42 })).toBe("42s ago");
    expect(formatAge({ has_data: true, age_seconds: 125 })).toBe("2m ago");
    expect(formatAge({ has_data: true, age_seconds: 7200 })).toBe("2h ago");
    expect(formatAge({ has_data: true, age_seconds: 172800 })).toBe("2d ago");
  });
});

describe("isStale", () => {
  it("is stale when never polled or over an hour old", () => {
    expect(isStale({ has_data: false, age_seconds: null })).toBe(true);
    expect(isStale({ has_data: true, age_seconds: 4000 })).toBe(true);
  });

  it("is fresh within the hour", () => {
    expect(isStale({ has_data: true, age_seconds: 30 })).toBe(false);
  });
});
