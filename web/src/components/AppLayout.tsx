import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LayoutGrid, ListOrdered, MonitorSpeaker, Briefcase, LogOut } from "lucide-react";
import { useSession, useLogout } from "@/features/auth/api";
import { Button } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";

const NAV = [
  { to: "/scenes", label: "Scenes", icon: LayoutGrid },
  { to: "/boards", label: "Boards", icon: MonitorSpeaker },
  { to: "/jobs", label: "Jobs", icon: Briefcase },
  { to: "/pipelines", label: "Pipelines", icon: ListOrdered },
];

export function AppLayout() {
  const { data: user } = useSession();
  const logout = useLogout();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 shrink-0 flex-col border-r border-neutral-800 bg-neutral-950">
        <div className="px-4 py-4 text-sm font-semibold tracking-tight text-neutral-100">
          artistaboard
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-2">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-neutral-800 text-neutral-100"
                    : "text-neutral-400 hover:bg-neutral-900 hover:text-neutral-200",
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-neutral-800 p-3">
          <div className="mb-2 truncate px-1 text-xs text-neutral-500">
            {user?.display_name || user?.email}
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start"
            onClick={async () => {
              await logout.mutateAsync();
              navigate("/login", { replace: true });
            }}
          >
            <LogOut className="h-4 w-4" /> Log out
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  );
}

export function PageHeader({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between border-b border-neutral-800 px-6 py-4">
      <h1 className="text-lg font-semibold text-neutral-100">{title}</h1>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}
