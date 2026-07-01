import { useState } from "react";
import { Plus, Plug, Pencil, Trash2, KeyRound } from "lucide-react";
import { PageHeader } from "@/components/AppLayout";
import { Button, Card, Badge, Spinner } from "@/components/ui/primitives";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/api/errors";
import type { Board } from "@/api/types";
import { useBoards, useDeleteBoard, useTestBoard } from "./api";
import { BoardFormDialog } from "./BoardFormDialog";

const STATUS_TONE: Record<string, "ok" | "warn" | "danger" | "neutral"> = {
  ok: "ok",
  unreachable: "danger",
  unconfigured: "neutral",
};

export function BoardsPage() {
  const { data: boards, isLoading } = useBoards();
  const deleteBoard = useDeleteBoard();
  const testBoard = useTestBoard();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Board | undefined>();
  const [busyId, setBusyId] = useState<string | null>(null);

  function openNew() {
    setEditing(undefined);
    setDialogOpen(true);
  }
  function openEdit(board: Board) {
    setEditing(board);
    setDialogOpen(true);
  }

  async function test(board: Board) {
    setBusyId(board.id);
    try {
      const result = await testBoard.mutateAsync(board.id);
      toast[result.status === "ok" ? "success" : "error"](
        result.status === "ok" ? "Board reachable" : `Board ${result.status}`,
      );
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Test failed");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(board: Board) {
    if (!confirm(`Delete board “${board.name}”?`)) return;
    setBusyId(board.id);
    try {
      await deleteBoard.mutateAsync(board.id);
      toast.success("Board deleted");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not delete board");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <PageHeader title="Boards">
        <Button onClick={openNew}>
          <Plus className="h-4 w-4" /> New board
        </Button>
      </PageHeader>

      <div className="p-6">
        {isLoading ? (
          <div className="flex justify-center py-16">
            <Spinner className="h-6 w-6" />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {boards?.map((board) => (
              <Card key={board.id} className="flex flex-col gap-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium text-neutral-100">{board.name}</div>
                    <div className="mt-0.5 text-xs text-neutral-500">{board.model}</div>
                  </div>
                  <Badge tone={STATUS_TONE[board.status] ?? "neutral"} className="shrink-0">
                    {board.status}
                  </Badge>
                </div>

                <div className="flex flex-col gap-1 text-xs text-neutral-500">
                  <span className="flex items-center gap-1.5">
                    <KeyRound className="h-3 w-3" />
                    {board.has_key ? `key •••• ${board.rw_key_last4}` : "no key set"}
                  </span>
                  {board.last_painted_at && (
                    <span>last painted {new Date(board.last_painted_at).toLocaleString()}</span>
                  )}
                </div>

                <div className="mt-auto flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => test(board)}
                    disabled={busyId === board.id || !board.has_key}
                  >
                    <Plug className="h-3.5 w-3.5" /> Test
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => openEdit(board)}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-400"
                    onClick={() => remove(board)}
                    disabled={busyId === board.id}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </Card>
            ))}
            {boards?.length === 0 && (
              <p className="text-sm text-neutral-500">No boards yet. Add one to connect a Vestaboard.</p>
            )}
          </div>
        )}
      </div>

      {/* Keyed so the form resets its local state between new/edit targets. */}
      <BoardFormDialog
        key={editing?.id ?? "new"}
        board={editing}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />
    </>
  );
}
