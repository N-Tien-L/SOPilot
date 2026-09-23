import {
  FileType,
  ProcessingStatus,
  ChunkingStrategy,
  EmbeddingModel,
} from "@/interfaces/enums/knowledge";

export interface Document {
  id: string;
  originalFilename: string;
  fileType: FileType;
  fileSizeBytes: number;
  mimeType: string;
  fileKey: string;
  bucketName: string;
  status: ProcessingStatus;
  currentVersion: number;
  extractedText?: string;
  pageCount: number;
  wordCount: number;
  language: string;
  ocrRequired: boolean;
  ocrConfidence?: number;
  chunkingStrategy: ChunkingStrategy;
  chunkSize: number;
  chunkOverlap: number;
  embeddingModel: EmbeddingModel;
  uploadedBy: string;
  createdAt: Date;
  updatedAt: Date;
  deletedAt?: Date;
}
