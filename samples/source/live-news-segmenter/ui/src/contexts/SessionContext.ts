import { useContext, createContext } from "react";
import { EventDto } from "@src/types";
import { AuthUser } from "aws-amplify/auth";

interface SessionContextProps {
    event: EventDto;
    setEvent: (event: EventDto) => void;
    user: AuthUser
}

export const SessionContext = createContext({} as SessionContextProps);

export function useSessionContext() {
    return useContext(SessionContext);
}