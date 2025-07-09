import { Input } from '@aws-amplify/ui-react';
import styled from 'styled-components';

import { AWS_BORDER_COLOR, AWS_DARKER } from '@src/theme';

export const BaseInput = styled(Input)`
  background: ${AWS_DARKER};
  border: 1px solid ${AWS_BORDER_COLOR};
  border-radius: 4px;
  font-size: 12px;

  &.amplify-input--error {
    border-color: var(--amplify-components-fieldcontrol-error-border-color);
  }
`;
