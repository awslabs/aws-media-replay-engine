import { AuthUser } from 'aws-amplify/auth';
import { FC, useState } from 'react';
import { Route, Routes } from 'react-router-dom';

import { SessionContext } from '@src/contexts';
import { Routes as RouteEnum } from '@src/enums';
import { ErrorPage, HomePage, NewsPage } from '@src/pages';
import { EventDto } from '@src/types';

interface MainProps {
  user: AuthUser;
}

export const Main: FC<MainProps> = ({ user }) => {
  const [event, setEvent] = useState({} as EventDto);

  return (
    <SessionContext.Provider value={{ event, setEvent, user }}>
      <Routes>
        <Route
          path={RouteEnum.HOME}
          element={<HomePage />}
          errorElement={<ErrorPage />}
        />
        <Route
          path={RouteEnum.NEWS_AGENT}
          element={<NewsPage />}
          errorElement={<ErrorPage />}
        />
      </Routes>
    </SessionContext.Provider>
  );
};
