export interface DocumentPopularity {
  id: string;
  documentId: string;
  totalCitations: number;
  uniqueQuestionsCited: number;
  citationsWithLikes: number;
  citationsWithDislikes: number;
  firstCitedAt: Date;
  lastCitedAt: Date;
  citationsLast7Days: number;
  citationsLast30Days: number;
  createdAt: Date;
  updatedAt: Date;
}
