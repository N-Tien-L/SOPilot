export interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string;
  parentId?: string;
  icon?: string;
  displayOrder: number;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}
