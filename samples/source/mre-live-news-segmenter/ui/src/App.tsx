import { Authenticator, ThemeProvider } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Amplify } from 'aws-amplify';
import { ErrorBoundary } from 'react-error-boundary';
import { BrowserRouter } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import 'rodal/lib/rodal.css';
import styled from 'styled-components';

import { API } from '@src/api/api-exports';
import { ErrorPage } from '@src/pages';
import { Main } from '@src/pages';
import { theme } from '@src/theme';
import { awsmobile } from '@src/utils';

const StyledAuthenticator = styled(Authenticator)`
  height: 100vh;
`;

Amplify.configure(awsmobile);
const existingConfig = Amplify.getConfig();
Amplify.configure({
  ...existingConfig, // <=== existingConfig instead of awsconfig
  API: {
    ...existingConfig.API,
    REST: {
      ...existingConfig.API?.REST,
      ...API,
    },
  },
});

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider theme={theme}>
          <ErrorBoundary fallback={<ErrorPage />}>
            <StyledAuthenticator
              hideSignUp={true}
              loginMechanisms={['username']}
            >
              {({ user }) =>
                user ? (
                  <>
                    <Main user={user} />
                    <ToastContainer
                      position="top-right"
                      autoClose={3000}
                      hideProgressBar
                      newestOnTop={false}
                      closeOnClick
                      rtl={false}
                      pauseOnFocusLoss
                      pauseOnHover
                    />
                  </>
                ) : (
                  <></>
                )
              }
            </StyledAuthenticator>
          </ErrorBoundary>
        </ThemeProvider>
        <ReactQueryDevtools />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
