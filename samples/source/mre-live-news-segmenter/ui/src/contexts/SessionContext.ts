import { AuthUser } from 'aws-amplify/auth';
import { createContext, useContext } from 'react';

import { EventDto } from '@src/types';

interface SessionContextProps {
  event: EventDto;
  setEvent: (event: EventDto) => void;
  user: AuthUser;
}

export const SessionContext = createContext({} as SessionContextProps);

export function useSessionContext() {
  return useContext(SessionContext);
}
