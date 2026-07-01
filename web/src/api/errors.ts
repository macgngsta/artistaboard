// FastAPI returns errors as {detail: string} for HTTPExceptions and
// {detail: [{loc, msg, type}, ...]} for 422 request-validation failures.
// This normalizes both into a single user-facing message + status.

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// An ApiError already carries a normalized user-facing message; anything else
// (network failure, unexpected throw) falls back to the caller's phrasing.
export function errorMessage(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.message : fallback;
}

type ValidationItem = { loc?: (string | number)[]; msg?: string };

export function messageFromDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = (detail as ValidationItem[])
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc.filter((p) => p !== "body").join(".") : "";
        return field ? `${field}: ${d.msg ?? "invalid"}` : (d.msg ?? "invalid");
      })
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }
  return fallback;
}

// openapi-fetch returns { data, error, response }; throw a normalized ApiError
// from `error` so callers (and TanStack Query) can surface a clean message.
export function toApiError(error: unknown, response: Response): ApiError {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  const msg = messageFromDetail(detail, response.statusText || "Request failed");
  return new ApiError(msg, response.status);
}
