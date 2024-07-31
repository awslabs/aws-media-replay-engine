import { Flex, View } from '@aws-amplify/ui-react';
import styled from 'styled-components';

import UpcomingEventImage from '@src/assets/upcoming-event.jpeg';

export const BackgroundImage = styled(View)`
  background-image: url(${UpcomingEventImage});
  background-size: cover;
  background-position: center;
  height: 100%;
  width: 100%;
  position: absolute;
  top: 0;
  left: 0;
  opacity: 0.2;
`;

export const Content = styled(Flex)`
  width: calc(50vw - 40px);
  z-index: 1;
  position: relative;

  button {
    width: 100px;
    height: 28px;
    font-size: 12px;
  }
`;
