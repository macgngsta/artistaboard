import { Briefcase, Database, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/AppLayout";
import { Card, Badge, Button, Spinner } from "@/components/ui/primitives";
import { toast } from "@/components/ui/toast";
import { errorMessage } from "@/api/errors";
import { useJobs, optionFields } from "@/features/pipelines/jobs";
import { useDataSources, usePollNow } from "./api";
import { formatAge, isStale } from "./freshness";

// Jobs page = the data-source management view. Top: the active data series the user's
// running boards reference, with per-series freshness and a manual "poll now" kick.
// Bottom: the read-only catalogue of built-in jobs and their typed options.
export function JobsPage() {
  const { data: jobs, isLoading } = useJobs();
  const { data: sources, isLoading: sourcesLoading } = useDataSources();
  const poll = usePollNow();

  const pollNow = () =>
    poll.mutate(undefined, {
      onSuccess: (r) =>
        toast[r.failed.length ? "error" : "success"](
          r.failed.length
            ? `Polled ${r.polled.length}, ${r.failed.length} failed`
            : r.polled.length
              ? `Polled ${r.polled.length} source${r.polled.length === 1 ? "" : "s"}`
              : "No running boards reference any data",
        ),
      onError: (e) => toast.error(errorMessage(e, "Poll failed")),
    });

  return (
    <>
      <PageHeader title="Jobs">
        <Button variant="secondary" size="sm" onClick={pollNow} disabled={poll.isPending}>
          <RefreshCw className={`h-4 w-4 ${poll.isPending ? "animate-spin" : ""}`} />
          Poll now
        </Button>
      </PageHeader>

      <div className="flex flex-col gap-8 p-6">
        <section className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-violet-400" />
            <h2 className="text-sm font-semibold text-neutral-200">Data sources</h2>
          </div>
          <p className="max-w-2xl text-sm text-neutral-400">
            The data series your <span className="text-neutral-200">running</span> boards reference.
            The poller keeps these fresh so boards paint from the database; a stale series means a
            board is falling back to a live fetch.
          </p>

          {sourcesLoading ? (
            <div className="flex justify-center py-8">
              <Spinner className="h-6 w-6" />
            </div>
          ) : sources && sources.length > 0 ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {sources.map((s) => (
                <Card key={`${s.source}:${s.source_key}`} className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-medium text-neutral-100">{s.source}</span>
                    {s.source_key && (
                      <span className="font-mono text-xs text-neutral-500">{s.source_key}</span>
                    )}
                  </div>
                  <Badge tone={isStale(s) ? "warn" : "ok"} className="self-start">
                    {formatAge(s)}
                  </Badge>
                </Card>
              ))}
            </div>
          ) : (
            <p className="text-sm text-neutral-500">
              No running boards reference any data yet. Start a board with a pipeline to see its
              sources here.
            </p>
          )}
        </section>

        <section className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Briefcase className="h-4 w-4 text-violet-400" />
            <h2 className="text-sm font-semibold text-neutral-200">Catalogue</h2>
          </div>
          <p className="max-w-2xl text-sm text-neutral-400">
            Built-in jobs fetch live data (times, transit, scores, now-playing…). Add a job directly to
            a pipeline, or set it as a scene entry's <span className="text-neutral-200">data source</span>{" "}
            to fill that scene's variables. Options can be overridden per pipeline entry.
          </p>

          {isLoading ? (
            <div className="flex justify-center py-8">
              <Spinner className="h-6 w-6" />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {jobs?.map((job) => {
                const options = optionFields(job.options_schema);
                return (
                  <Card key={job.name} className="flex flex-col gap-3">
                    <div className="flex items-center gap-2">
                      <Briefcase className="h-4 w-4 text-violet-400" />
                      <span className="font-mono font-medium text-neutral-100">{job.name}</span>
                    </div>

                    {options.length === 0 ? (
                      <p className="text-xs text-neutral-500">No options.</p>
                    ) : (
                      <div className="flex flex-col gap-1.5">
                        <div className="text-xs font-medium text-neutral-400">Options</div>
                        <div className="flex flex-wrap gap-1.5">
                          {options.map((o) => (
                            <Badge key={o.name} tone="neutral" title={`${o.name} (${o.kind})`}>
                              {o.title}
                              <span className="ml-1 text-neutral-500">· {o.kind}</span>
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </Card>
                );
              })}
              {jobs?.length === 0 && <p className="text-sm text-neutral-500">No jobs available.</p>}
            </div>
          )}
        </section>
      </div>
    </>
  );
}
