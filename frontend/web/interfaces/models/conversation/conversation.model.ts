export interface Conversation {
  id: string;
  userId: string;
  title: string;
  messageCount: number;
  lastMessageAt: Date;
  createdAt: Date;
  updatedAt: Date;
  deletedAt?: Date;
}
