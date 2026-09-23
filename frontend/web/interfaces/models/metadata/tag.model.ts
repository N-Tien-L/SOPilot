export interface Tag {
  id: string;
  name: string;
  slug: string;
  color?: string;
  usageCount: number;
  createdAt: Date;
}
