import { Briefcase } from "lucide-react";
import { PageHeader } from "@/components/AppLayout";
import { Card, Badge, Spinner } from "@/components/ui/primitives";
import { useJobs, optionFields } from "@/features/pipelines/jobs";

// Read-only catalogue of the built-in jobs and the typed options each accepts.
// Jobs are data sources: use one directly in a pipeline, or as a scene entry's
// data source to fill that scene's variables. (Scheduling / data-freshness
// management will arrive with the data-layer API.)
export function JobsPage() {
  const { data: jobs, isLoading } = useJobs();

  return (
    <>
      <PageHeader title="Jobs" />

      <div className="p-6">
        <p className="mb-4 max-w-2xl text-sm text-neutral-400">
          Built-in jobs fetch live data (times, transit, scores, now-playing…). Add a job directly to
          a pipeline, or set it as a scene entry's <span className="text-neutral-200">data source</span>{" "}
          to fill that scene's variables. Options can be overridden per pipeline entry.
        </p>

        {isLoading ? (
          <div className="flex justify-center py-16">
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
            {jobs?.length === 0 && (
              <p className="text-sm text-neutral-500">No jobs available.</p>
            )}
          </div>
        )}
      </div>
    </>
  );
}
