import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import { SortableContext, arrayMove, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { ArrowLeft, Plus, Save, Play, Repeat } from "lucide-react";
import { PageHeader } from "@/components/AppLayout";
import { Button, Card, Input, Spinner } from "@/components/ui/primitives";
import { Switch } from "@/components/ui/switch";
import { Select } from "@/components/ui/select";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/api/errors";
import type { PipelineIn } from "@/api/types";
import { useScenes } from "@/features/scenes/api";
import { useBoards, useAssignPipeline, useStartBoard } from "@/features/boards/api";
import { usePipeline, useUpdatePipeline } from "./api";
import { useJobs } from "./jobs";
import { PipelineEntryRow } from "./PipelineEntryRow";
import { NowPlaying } from "./NowPlaying";
import { emptyEntry, fromPipeline, toEntryIn, type WorkingEntry } from "./entry";

export function PipelineEditorPage() {
  const { pipelineId } = useParams();
  const navigate = useNavigate();
  const { data: pipeline, isLoading } = usePipeline(pipelineId);
  const { data: scenes } = useScenes();
  const { data: boards } = useBoards();
  const { data: jobs } = useJobs();

  const [name, setName] = useState("");
  const [loop, setLoop] = useState(true);
  const [entries, setEntries] = useState<WorkingEntry[]>([]);
  const [loadedId, setLoadedId] = useState<string | null>(null);
  const [boardId, setBoardId] = useState("");

  const update = useUpdatePipeline();
  const assign = useAssignPipeline();
  const start = useStartBoard();
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));

  useEffect(() => {
    if (pipeline && pipeline.id !== loadedId) {
      setName(pipeline.name);
      setLoop(pipeline.loop);
      setEntries(fromPipeline(pipeline));
      setLoadedId(pipeline.id);
    }
  }, [pipeline, loadedId]);

  if (isLoading || loadedId !== pipelineId) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  function patchEntry(key: string, patch: Partial<WorkingEntry>) {
    setEntries((es) => es.map((e) => (e.key === key ? { ...e, ...patch } : e)));
  }
  function removeEntry(key: string) {
    setEntries((es) => es.filter((e) => e.key !== key));
  }
  function onDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setEntries((es) => {
        const from = es.findIndex((e) => e.key === active.id);
        const to = es.findIndex((e) => e.key === over.id);
        return arrayMove(es, from, to);
      });
    }
  }

  function buildBody(): PipelineIn {
    return { name: name || "Untitled pipeline", loop, entries: entries.map(toEntryIn) };
  }

  async function save(): Promise<boolean> {
    try {
      await update.mutateAsync({ id: loadedId!, body: buildBody() });
      toast.success("Pipeline saved");
      return true;
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save pipeline");
      return false;
    }
  }

  // Save-then-run so the board always shows exactly what's on screen.
  async function run() {
    if (!boardId) {
      toast.error("Pick a board first");
      return;
    }
    if (!(await save())) return;
    try {
      await assign.mutateAsync({ boardId, pipelineId: loadedId! });
      await start.mutateAsync(boardId);
      toast.success("Running on board");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not start");
    }
  }

  const boardOptions = (boards ?? []).map((b) => ({ value: b.id, label: b.name }));
  const selectedBoard = boards?.find((b) => b.id === boardId);
  const running = assign.isPending || start.isPending;

  return (
    <>
      <PageHeader title="Pipeline editor">
        <Button variant="ghost" size="sm" onClick={() => navigate("/pipelines")}>
          <ArrowLeft className="h-4 w-4" /> Pipelines
        </Button>
        <Button onClick={save} disabled={update.isPending}>
          {update.isPending ? <Spinner /> : <Save className="h-4 w-4" />} Save
        </Button>
      </PageHeader>

      <div className="grid grid-cols-1 gap-4 p-6 lg:grid-cols-[1fr_320px]">
        {/* Left: pipeline config + entries */}
        <div className="flex flex-col gap-4">
          <Card className="flex flex-wrap items-center gap-4">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Pipeline name"
              className="max-w-xs font-medium"
            />
            <label className="flex items-center gap-2 text-sm text-neutral-300">
              <Repeat className="h-4 w-4 text-neutral-500" />
              Loop
              <Switch checked={loop} onCheckedChange={setLoop} />
            </label>
          </Card>

          <div className="flex flex-col gap-2">
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              modifiers={[restrictToVerticalAxis]}
              onDragEnd={onDragEnd}
            >
              <SortableContext items={entries.map((e) => e.key)} strategy={verticalListSortingStrategy}>
                {entries.map((entry) => (
                  <PipelineEntryRow
                    key={entry.key}
                    entry={entry}
                    scenes={scenes ?? []}
                    jobs={jobs ?? []}
                    onChange={(patch) => patchEntry(entry.key, patch)}
                    onRemove={() => removeEntry(entry.key)}
                  />
                ))}
              </SortableContext>
            </DndContext>

            {entries.length === 0 && (
              <p className="py-4 text-sm text-neutral-500">
                No entries yet. Add a job or scene to sequence on the board.
              </p>
            )}

            <Button
              variant="outline"
              size="sm"
              className="self-start"
              onClick={() => setEntries((es) => [...es, emptyEntry()])}
            >
              <Plus className="h-4 w-4" /> Add entry
            </Button>
          </div>
        </div>

        {/* Right: run on a board + now playing */}
        <Card className="flex h-fit flex-col gap-4">
          <div className="text-sm font-medium text-neutral-200">Run on board</div>
          <Select
            value={boardId}
            options={boardOptions}
            placeholder={boardOptions.length ? "Select a board" : "No boards yet"}
            onValueChange={setBoardId}
          />
          <Button onClick={run} disabled={running || !boardId || entries.length === 0}>
            {running ? <Spinner /> : <Play className="h-4 w-4" />} Run on board
          </Button>

          {selectedBoard && pipeline && (
            <div className="border-t border-neutral-800 pt-4">
              <NowPlaying boardId={selectedBoard.id} pipeline={pipeline} />
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
