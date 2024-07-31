import { Placeholder, View } from '@aws-amplify/ui-react';
import { FC, useMemo } from 'react';

import { FollowTopics, SearchPanel } from './components';
import { StyledTabs } from './style';

interface RightPanelProps {
  isLoadingFollowTopics: boolean;
}

export const RightPanel: FC<RightPanelProps> = ({ isLoadingFollowTopics }) => {
  const isLoading = useMemo(() => {
    return isLoadingFollowTopics;
  }, [isLoadingFollowTopics]);

  return (
    <View flex={1} position={'relative'}>
      <StyledTabs
        width="100%"
        justifyContent="flex-start"
        defaultValue="Follow Topics"
        items={[
          {
            label: 'Follow Topics',
            value: 'Follow Topics',
            content: isLoading ? (
              <Placeholder size="large" height={97} />
            ) : (
              <FollowTopics />
            ),
          },
        ]}
      />
      <SearchPanel isLoading={isLoading} />
    </View>
  );
};
