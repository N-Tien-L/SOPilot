export interface DepartmentDailyStat {
  id: string;
  date: Date;
  departmentId: string;
  totalQuestions: number;
  uniqueUsers: number;
  likes: number;
  dislikes: number;
  topCategories?: Record<string, unknown>;
  computedAt: Date;
}
