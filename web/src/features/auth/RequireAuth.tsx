import { Navigate, Outlet } from "react-router-dom";
import { useSession } from "./api";
import { Spinner } from "@/components/ui/primitives";

// Gate for authenticated routes: wait for GET /me, redirect to /login on 401.
export function RequireAuth() {
  const { data: user, isLoading } = useSession();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}
