import { View } from '@aws-amplify/ui-react';
import styled from 'styled-components';

import { BaseButton } from '@src/components';
import { AWS_BORDER_COLOR } from '@src/theme';

export const StyledView = styled(View)`
  border-right: 1px solid ${AWS_BORDER_COLOR};
  border-left: 1px solid ${AWS_BORDER_COLOR};
  height: calc(100vh - 54px);
`;

export const LoadMoreButton = styled(BaseButton)`
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    bottom: 0px;
    font-size: 12px;
    font-weight: 700;
    height: 30px;
    z-index: 2;
`;