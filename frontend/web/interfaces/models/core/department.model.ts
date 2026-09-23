export interface Department {
  id: string;
  name: string;
  code: string;
  description?: string;
  parentId?: string;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}
