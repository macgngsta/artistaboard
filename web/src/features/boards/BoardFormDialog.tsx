import { useState } from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button, Field, Input, Spinner } from "@/components/ui/primitives";
import { Select } from "@/components/ui/select";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/api/errors";
import { BOARD_MODELS, type Board, type BoardIn } from "@/api/types";
import { useCreateBoard, useUpdateBoard } from "./api";

const MODEL_OPTIONS = BOARD_MODELS.map((m) => ({ value: m, label: m }));

// Create/edit a board. The rw_key is write-only: on edit it is only sent when the
// user types a new one (an empty value keeps the existing key server-side). We
// never render the stored key — only has_key + last4 come back.
export function BoardFormDialog({
  board,
  open,
  onOpenChange,
}: {
  board?: Board;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const editing = !!board;
  const [name, setName] = useState(board?.name ?? "");
  const [model, setModel] = useState(board?.model ?? "flagship");
  const [minInterval, setMinInterval] = useState(String(board?.min_send_interval ?? 15));
  const [rwKey, setRwKey] = useState("");

  const create = useCreateBoard();
  const update = useUpdateBoard();
  const pending = create.isPending || update.isPending;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const body: BoardIn = {
      name,
      model,
      rw_key: rwKey, // empty on edit => backend keeps the existing key
      min_send_interval: Number(minInterval) || 15,
    };
    try {
      if (editing) await update.mutateAsync({ id: board.id, body });
      else await create.mutateAsync(body);
      toast.success(editing ? "Board updated" : "Board created");
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save board");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={editing ? "Edit board" : "New board"}>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field label="Name">
            <Input value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
          </Field>
          <Field label="Model">
            <Select value={model} onValueChange={setModel} options={MODEL_OPTIONS} />
          </Field>
          <Field label="Minimum send interval (seconds)">
            <Input
              type="number"
              min={1}
              value={minInterval}
              onChange={(e) => setMinInterval(e.target.value)}
            />
          </Field>
          <Field label="Read/Write API key">
            <Input
              type="password"
              value={rwKey}
              onChange={(e) => setRwKey(e.target.value)}
              placeholder={
                editing
                  ? board.has_key
                    ? `•••• ${board.rw_key_last4} — leave blank to keep`
                    : "no key set"
                  : "Vestaboard R/W key"
              }
              autoComplete="off"
            />
          </Field>
          <p className="-mt-2 text-xs text-neutral-500">
            The key is write-only and stored encrypted; it is never shown again.
          </p>

          <div className="mt-1 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending}>
              {pending ? <Spinner /> : editing ? "Save" : "Create"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
