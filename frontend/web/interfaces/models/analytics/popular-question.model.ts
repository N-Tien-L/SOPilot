export interface PopularQuestion {
  id: string;
  questionNormalized: string;
  questionSample: string;
  askCount: number;
  uniqueUsersCount: number;
  firstAskedAt: Date;
  lastAskedAt: Date;
  totalLikes: number;
  totalDislikes: number;
  commonSourceDocuments?: Record<string, unknown>;
  detectedCategory?: string;
  detectedDepartmentId?: string;
  createdAt: Date;
  updatedAt: Date;
}
