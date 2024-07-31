import { Button, Flex, Text, View } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react';
import { ChangeEvent, FC, useState } from 'react';
import { toast } from 'react-toastify';
import styled from 'styled-components';

import { BaseButton, BaseInput, BaseModal } from '@src/components';
import { useSessionContext } from '@src/contexts';
import { AWS_BORDER_COLOR } from '@src/theme';
import { BaseFunction } from '@src/types';
import { formatDate } from '@src/utils';

interface ModalNotifyProps {
  visible: boolean;
  onClose: BaseFunction;
  onSuccess: BaseFunction;
}

const StyledView = styled(View)`
  border: 1px solid ${AWS_BORDER_COLOR};
  padding: 15px;
`;

export const ModalNotify: FC<ModalNotifyProps> = ({
  visible,
  onClose,
  onSuccess,
}) => {
  const [email, setEmail] = useState('');
  const [hasError, setHasError] = useState(false);

  const { event } = useSessionContext();

  const handleClose = () => {
    setHasError(false);
    setEmail('');
    onClose();
  };

  const handleSuccess = () => {
    if (email.length === 0) {
      setHasError(true);
      toast.error('Please enter your email address');
    } else {
      if (email.match(/^[\w-.]+@([\w-]+\.)+[\w-]{2,4}$/g) === null) {
        setHasError(true);
        toast.error('Please enter a valid email address');
      } else {
        setHasError(false);
        onSuccess();
        handleClose();
      }
    }
  };

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    setHasError(false);
    setEmail(e.target.value);
  };

  return (
    <BaseModal
      visible={visible}
      onClose={handleClose}
      header="Notify when event starts"
      content={
        <Flex direction="column">
          <Text fontSize={12}>
            We will send you a notification as soon as this event starts.
          </Text>
          <StyledView>
            <Text fontWeight={500}>{event.Name}</Text>
            <Text fontSize={12} fontWeight={200}>
              {formatDate(event.Start, 'MMMM d, yyyy @ h:mma z')}
            </Text>
          </StyledView>
          <BaseInput
            placeholder="Enter email address"
            value={email}
            onChange={handleInputChange}
            hasError={hasError}
          />
        </Flex>
      }
      footer={
        <>
          <Button onClick={handleClose} variation="link">
            Cancel
          </Button>
          <BaseButton onClick={handleSuccess} variation="primary">
            Save
          </BaseButton>
        </>
      }
      width={396}
    />
  );
};
