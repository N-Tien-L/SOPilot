import { EmbeddingModel } from "@/interfaces/enums/knowledge";

export interface EmbeddingCache {
  id: string;
  textHash: string;
  textLength: number;
  embeddingModel: EmbeddingModel;
  embeddingDimension: number;
  usageCount: number;
  lastUsedAt: Date;
  createdAt: Date;
}
