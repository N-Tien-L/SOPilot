export interface HourlyAggregate {
  id: string;
  datetime: Date;
  hour: number;
  totalQuestions: number;
  totalRequests: number;
  totalErrors: number;
  uniqueUsers: number;
  avgResponseTimeMs: number;
  likes: number;
  dislikes: number;
  computedAt: Date;
}
