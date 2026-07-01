import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useLogin, useRegister } from "./api";
import { ApiError } from "@/api/errors";
import { Button, Card, Field, Input, Spinner } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";

type Mode = "login" | "register";

export function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const login = useLogin();
  const register = useRegister();
  const pending = login.isPending || register.isPending;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      if (mode === "login") {
        await login.mutateAsync({ email, password });
      } else {
        await register.mutateAsync({ email, password, display_name: displayName });
      }
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        // A closed registration means an owner already exists — nudge to login.
        if (mode === "register" && err.status === 403) {
          setMode("login");
          setError("Registration is closed. Log in with an existing account.");
          return;
        }
        setError(err.message);
      } else {
        setError("Something went wrong. Please try again.");
      }
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm p-6">
        <h1 className="mb-1 text-lg font-semibold text-neutral-100">artistaboard</h1>
        <p className="mb-5 text-sm text-neutral-400">
          {mode === "login" ? "Sign in to your account" : "Create an account"}
        </p>

        <div className="mb-5 flex rounded-md border border-neutral-800 p-0.5 text-sm">
          {(["login", "register"] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => {
                setMode(m);
                setError(null);
              }}
              className={cn(
                "flex-1 rounded px-3 py-1.5 capitalize transition-colors",
                mode === m ? "bg-neutral-800 text-neutral-100" : "text-neutral-400",
              )}
            >
              {m === "register" ? "Register" : "Log in"}
            </button>
          ))}
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          {mode === "register" && (
            <Field label="Display name (optional)">
              <Input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                autoComplete="name"
              />
            </Field>
          )}
          <Field label="Email">
            <Input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </Field>
          <Field label="Password">
            <Input
              type="password"
              required
              minLength={mode === "register" ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </Field>
          {mode === "register" && (
            <p className="-mt-2 text-xs text-neutral-500">
              The first account becomes the owner. Password must be at least 8 characters.
            </p>
          )}

          {error && (
            <p className="rounded-md border border-red-900 bg-red-950/50 px-3 py-2 text-sm text-red-300">
              {error}
            </p>
          )}

          <Button type="submit" disabled={pending} className="mt-1">
            {pending ? <Spinner /> : mode === "login" ? "Log in" : "Create account"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
