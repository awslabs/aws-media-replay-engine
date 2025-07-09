import { Flex, Heading } from '@aws-amplify/ui-react';

import { BaseButton } from '@src/components';
import { PageIds, Routes } from '@src/enums';
import { PageLayout } from '@src/layout';

export const ErrorPage = () => {
  return (
    <PageLayout pageId={PageIds.ERROR_PAGE} fullScreen>
      <Flex
        direction="column"
        justifyContent={'center'}
        alignItems={'center'}
        height={'90%'}
      >
        <Heading level={1}>Oops!</Heading>
        <p>Sorry, an unexpected error has occurred.</p>
        <BaseButton
          variation="primary"
          onClick={() => window.location.replace(Routes.HOME)}
        >
          Return to home
        </BaseButton>
      </Flex>
    </PageLayout>
  );
};
