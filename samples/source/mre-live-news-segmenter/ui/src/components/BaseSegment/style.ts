import { Card } from '@aws-amplify/ui-react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import styled from 'styled-components';

import { AWS_BORDER_COLOR } from '@src/theme';

export const StlyedCard = styled(Card)`
  border-top: unset;
  border-left: unset;
  border-right: unset;
  position: relative;

  &.position-1 {
    border-top: 1px solid ${AWS_BORDER_COLOR};
  }

  .icon--xmark {
    display: none;
  }

  .segment__summary {
    font-size: 12px;
    font-weight: 400;
    margin-top: 7px;
    margin-bottom: 18px;
  }

  .icon--heart {
    position: absolute;
    bottom: 14px;
    right: 16px;
    line-height: 0;
  }

  &.icon__close--visible {
    padding-right: 32px;
    position: relative;

    .icon--xmark {
      display: block;
      position: absolute;
      top: 16px;
      right: 16px;
    }

    .segment__summary {
      margin-bottom: 12px;
    }

    .icon--heart {
      display: none;
    }
  }

  .lazy-load-image-background.blur {
    background-color: ${AWS_BORDER_COLOR};

    &.lazy-load-image-loaded {
      background-color: unset;
    }
  }
`;

export const StyledIcon = styled(FontAwesomeIcon)`
  cursor: pointer;
  width: 12px;
`;
