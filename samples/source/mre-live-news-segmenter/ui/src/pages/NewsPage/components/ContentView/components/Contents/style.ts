import { Flex } from '@aws-amplify/ui-react';
import styled from 'styled-components';

import { BaseButton } from '@src/components';
import { AWS_ORANGE, WHITE } from '@src/theme';

export const ButtonGroup = styled(Flex)`
  font-size: 12px;
  font-weight: 700;
  border-radius: 14px;
  color: ${AWS_ORANGE};
  gap: 0;
  cursor: pointer;

  > div {
    &:first-of-type {
      border-bottom-left-radius: 14px;
      border-top-left-radius: 14px;
      padding: 5px 20px;
      border: 1px solid ${AWS_ORANGE};
    }

    &:last-of-type {
      border-bottom-right-radius: 14px;
      border-top-right-radius: 14px;
      padding: 5px 20px;
      border: 1px solid ${AWS_ORANGE};
    }
  }

  & .active {
    border: unset;
    background-color: ${AWS_ORANGE};
    color: ${WHITE};
  }
`;

export const SearchButton = styled(BaseButton)`
  font-size: 12px;
  font-weight: 700;
  height: 30px;
  z-index: 2;
  box-shadow: none !important;

  > span {
    margin-right: 7px;
  }
`;
