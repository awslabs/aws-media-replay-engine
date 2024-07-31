import { Flex, Text, View } from '@aws-amplify/ui-react';
import {
  faBell,
  faCircleCheck,
  faHourglassHalf,
} from '@fortawesome/free-regular-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { FC } from 'react';

import { BaseButton } from '@src/components';
import { ModalNotify } from '@src/modals';
import { BaseFunction } from '@src/types';

interface QueuedViewProps {
  setNotifyModalVisibility: (value: boolean) => void;
  isNotified: boolean;
  notifyModalVisibility: boolean;
  handleNotifySuccess: BaseFunction;
}

export const QueuedView: FC<QueuedViewProps> = ({
  setNotifyModalVisibility,
  isNotified,
  notifyModalVisibility,
  handleNotifySuccess,
}) => {
  return (
    <>
      <Flex
        justifyContent="center"
        alignItems="center"
        direction="column"
        height="100%"
      >
        <Text variation="primary" fontWeight={700} fontSize="24px">
          Hang Tight, Event has not started!
        </Text>
        <View margin="25px 0">
          <FontAwesomeIcon
            icon={faHourglassHalf}
            fontSize={100}
            color="#4F5965"
          />
        </View>
        <BaseButton
          variation="primary"
          onClick={() => {
            setNotifyModalVisibility(true);
          }}
          disabled={isNotified}
        >
          <View margin="0 6px 0 0">
            <FontAwesomeIcon icon={isNotified ? faCircleCheck : faBell} />
          </View>
          Notify me when event starts
        </BaseButton>
      </Flex>
      <ModalNotify
        visible={notifyModalVisibility}
        onClose={() => setNotifyModalVisibility(false)}
        onSuccess={handleNotifySuccess}
      />
    </>
  );
};
