export interface UserProfile {
  id: string;
  userId: string;
  fullName: string;
  phone?: string;
  position?: string;
  avatarUrl?: string;
  bio?: string;
  dateOfBirth?: Date;
  employeeCode?: string;
  joinedDate: Date;
  createdAt: Date;
  updatedAt: Date;
}
