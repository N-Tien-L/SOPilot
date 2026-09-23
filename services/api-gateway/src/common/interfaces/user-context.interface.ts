declare global {
  namespace Express {
    interface Request {
      user?: import('./jwt-payload.interface').IUserContext;
      traceId?: string;
    }
  }
}

export {};
