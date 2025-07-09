import { SelectField } from '@aws-amplify/ui-react';
import styled from 'styled-components';

import { AWS_BORDER_COLOR } from '@src/theme';

export const BaseSelectField = styled(SelectField)`
  select {
    border: 1px solid ${AWS_BORDER_COLOR};
    border-radius: 14px;
    background-color: transparent;
    font-size: 12px;
    padding: 5px 48px 5px 16px;
  }
`;
