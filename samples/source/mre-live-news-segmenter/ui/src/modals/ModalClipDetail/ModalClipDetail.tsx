import { View } from '@aws-amplify/ui-react';
import { FC, useRef, useState } from 'react';

import { Video } from './components';

import { BaseButton, BaseModal } from '@src/components';
import { BaseFunction, ChildThemeDto } from '@src/types';

interface ModalClipDetailProps {
  visible: boolean;
  onClose: BaseFunction;
  segment: ChildThemeDto;
}

export const ModalClipDetail: FC<ModalClipDetailProps> = ({
  visible,
  onClose,
  segment,
}) => {
  const [shouldStopVideo, setShouldStopVideo] = useState(true);

  const endMarkerRef = useRef<HTMLDivElement>(null);

  const handleClose = () => {
    onClose();
    // Reset states
    setShouldStopVideo(true);

    if (endMarkerRef.current) {
      endMarkerRef.current.style.display = 'block';
      endMarkerRef.current.style.left = '0';
      endMarkerRef.current.style.visibility = 'hidden';
    }
  };

  return (
    <BaseModal
      visible={visible}
      onClose={handleClose}
      header={segment.Label}
      content={
        <View textAlign={'center'}>
          {visible && (
            <Video
              shouldStopVideo={shouldStopVideo}
              setShouldStopVideo={setShouldStopVideo}
              endMarkerRef={endMarkerRef}
              visible={visible}
            />
          )}
        </View>
      }
      footer={
        <BaseButton onClick={handleClose} variation="primary">
          Close
        </BaseButton>
      }
      width={1000}
    />
  );
};
