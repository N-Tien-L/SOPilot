// Department Types
export interface Department {
  id: string;
  name: string;
  code: string;
  description?: string;
  parent?: DepartmentInfo;
  isActive: boolean;
  userCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface DepartmentInfo {
  id: string;
  name: string;
  code: string;
}

export interface DepartmentTreeNode {
  id: string;
  name: string;
  code: string;
  isActive: boolean;
  description?: string;
  parent?: DepartmentInfo;
  userCount?: number;
  createdAt?: string;
  updatedAt?: string;
  children: DepartmentTreeNode[];
}

export interface CreateDepartmentRequest {
  name: string;
  code: string;
  description?: string;
  parentId?: string;
}

export interface UpdateDepartmentRequest {
  name?: string;
  description?: string;
  parentId?: string;
  isActive?: boolean;
}

export interface AssignUserDepartmentRequest {
  userId: string;
  departmentId: string;
}
