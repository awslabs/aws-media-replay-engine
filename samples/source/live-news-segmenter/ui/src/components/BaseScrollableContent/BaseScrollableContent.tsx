import { View } from '@aws-amplify/ui-react';
import styled from 'styled-components';

import { AWS_ORANGE } from '@src/theme';

export const BaseScrollableContent = styled(View)`
  overflow-y: auto;

  /* width */
  &::-webkit-scrollbar {
    width: 10px;
  }

  /* Track */
  &::-webkit-scrollbar-track {
    background: #f1f1f1;
  }

  /* Handle */
  &::-webkit-scrollbar-thumb {
    background: ${AWS_ORANGE};
  }

  /* Handle on hover */
  &::-webkit-scrollbar-thumb:hover {
    background: #555;
  }
`;
