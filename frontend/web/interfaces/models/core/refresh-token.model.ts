export interface RefreshToken {
  id: string;
  userId: string;
  tokenHash: string;
  deviceInfo: string;
  ipAddress: string;
  userAgent: string;
  expiresAt: Date;
  revoked: boolean;
  revokedAt?: Date;
  revokedReason?: string;
  replacedBy?: string;
  createdAt: Date;
}
