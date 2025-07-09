import styled from 'styled-components';

import { BaseButton, BaseLoadingButton } from '@src/components';

export const StyledButton = styled(BaseButton)`
  font-size: 12px;
  font-weight: 700;

  > span {
    margin-right: 10px;
  }
`;

export const StyledLoadingButton = styled(BaseLoadingButton)`
  font-size: 12px;
  font-weight: 700;

  > span {
    margin-right: 10px;
  }
`;
