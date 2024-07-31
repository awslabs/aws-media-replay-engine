import { FC, ReactNode } from 'react';

import { StyledPageLayout } from './style';

import { BaseLoader } from '@src/components';
import { useLoading } from '@src/hooks';
import { AppBar } from '@src/layout';
import { getGeneralLoading } from '@src/utils';

interface PageLayoutProps {
  pageId: string;
  children: ReactNode;
  fullScreen?: boolean;
}

export const PageLayout: FC<PageLayoutProps> = ({
  pageId,
  children,
  fullScreen,
}) => {
  const loading = useLoading();
  const generalLoading = getGeneralLoading();

  return (
    <StyledPageLayout id={pageId} height={fullScreen ? '100vh' : undefined}>
      {loading && generalLoading && <BaseLoader />}
      <AppBar pageId={pageId} />
      {children}
    </StyledPageLayout>
  );
};
