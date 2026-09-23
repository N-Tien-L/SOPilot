import { createParamDecorator, ExecutionContext } from '@nestjs/common';
import { IUserContext } from '../interfaces';

export const CurrentUser = createParamDecorator(
  (
    data: keyof IUserContext | undefined,
    ctx: ExecutionContext,
  ): IUserContext | unknown => {
    const request = ctx.switchToHttp().getRequest();
    const user = request.user as IUserContext;

    if (!user) {
      return null;
    }

    return data ? user[data] : user;
  },
);
