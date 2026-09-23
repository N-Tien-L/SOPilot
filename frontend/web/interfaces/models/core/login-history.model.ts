export interface LoginHistory {
  id: string;
  userId: string;
  username: string;
  ipAddress: string;
  userAgent: string;
  deviceType: string;
  location?: string;
  status: string;
  failureReason?: string;
  createdAt: Date;
}
