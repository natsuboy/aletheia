import { useProjectStore } from '@/stores';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, XCircle, Clock } from 'lucide-react';

export function IngestProgress() {
  const { indexingJobs } = useProjectStore();

  if (indexingJobs.size === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">索引任务</h3>
      {Array.from(indexingJobs.entries()).map(([jobId, job]) => (
        <Card key={jobId}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                {job.status === 'completed' && (
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                )}
                {job.status === 'failed' && (
                  <XCircle className="h-4 w-4 text-red-600" />
                )}
                {(job.status === 'pending' || job.status === 'running') && (
                  <Clock className="h-4 w-4 text-blue-600" />
                )}
                任务 {jobId.slice(0, 8)}
              </CardTitle>
              <Badge
                variant={
                  job.status === 'completed'
                    ? 'default'
                    : job.status === 'failed'
                    ? 'destructive'
                    : 'secondary'
                }
              >
                {job.status}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {job.message && (
              <p className="text-sm text-muted-foreground mb-2">{job.message}</p>
            )}
            {job.progress !== undefined && (
              <Progress value={job.progress} className="mb-2" />
            )}
            {job.error && (
              <p className="text-sm text-destructive">{job.error}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
