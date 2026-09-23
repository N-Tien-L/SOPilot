import { EmbeddingModel } from "@/interfaces/enums/knowledge";

export interface Chunk {
  id: string;
  documentId: string;
  documentVersion: number;
  chunkIndex: number;
  content: string;
  contentLength: number;
  tokenCount: number;
  pageNumber: number;
  startCharIndex: number;
  endCharIndex: number;
  embeddingModel: EmbeddingModel;
  embeddingDimension: number;
  vectorIndexed: boolean;
  vectorId?: string;
  departmentId: string;
  documentType: string;
  effectiveDate: Date;
  expiryDate?: Date;
  metadata?: Record<string, unknown>;
  createdAt: Date;
  updatedAt: Date;
}
