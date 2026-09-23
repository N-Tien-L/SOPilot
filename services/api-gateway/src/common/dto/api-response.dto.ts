export interface IApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  timestamp: string;
  traceId?: string;
}

export interface IPaginatedResponse<T> extends IApiResponse<T> {
  pagination?: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

export class ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  timestamp: string;
  traceId?: string;

  constructor(data?: T, message?: string, traceId?: string) {
    this.success = true;
    this.data = data;
    this.message = message;
    this.timestamp = new Date().toISOString();
    this.traceId = traceId;
  }

  static success<T>(
    data?: T,
    message?: string,
    traceId?: string,
  ): IApiResponse<T> {
    return {
      success: true,
      data,
      message,
      timestamp: new Date().toISOString(),
      traceId,
    };
  }

  static paginated<T>(
    data: T,
    pagination: { page: number; limit: number; total: number },
    traceId?: string,
  ): IPaginatedResponse<T> {
    return {
      success: true,
      data,
      timestamp: new Date().toISOString(),
      traceId,
      pagination: {
        ...pagination,
        totalPages: Math.ceil(pagination.total / pagination.limit),
      },
    };
  }
}
