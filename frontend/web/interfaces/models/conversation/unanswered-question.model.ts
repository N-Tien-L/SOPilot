export interface UnansweredQuestion {
  id: string;
  userId: string;
  messageId: string;
  conversationId: string;
  question: string;
  questionNormalized: string;
  attemptedContext?: Record<string, unknown>;
  searchQuery: string;
  topSimilarityScore: number;
  userDepartmentId: string;
  userRole: string;
  resolved: boolean;
  resolvedBy?: string;
  resolvedAt?: Date;
  resolutionNotes?: string;
  relatedDocumentId?: string;
  category?: string;
  priority?: string;
  createdAt: Date;
  updatedAt: Date;
}
