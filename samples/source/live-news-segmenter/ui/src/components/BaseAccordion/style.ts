import { Accordion } from '@aws-amplify/ui-react';
import styled from 'styled-components';

import { AWS_BORDER_COLOR, AWS_DARKER } from '@src/theme';

export const StyledAccordion = styled(Accordion.Container)`
  border-radius: unset;
  background-color: ${AWS_DARKER};

  .amplify-accordion__item {
    border: unset;

    summary {
      [data-icon='caret-up'] {
        display: none;
      }
  
      .icon--loader {
        display: none;
      }
    }

    &[open] {
      summary {
        [data-icon='caret-down'] {
          display: none;
        }
  
        [data-icon='caret-up'] {
          display: block;
        }
  
        .icon--loader {
          &.is--loading {
            display: block;
          }
        }
      }
      }

  }

  .amplify-accordion__item__content {
    padding: 0;
  }
`;

export const StyledTrigger = styled(Accordion.Trigger)`
  background-color: #687078;
  font-size: 14px;
  font-weight: 700;
  border-radius: unset;
  border: 1px solid ${AWS_BORDER_COLOR};
  border-left: unset;
  border-right: unset;
  justify-content: space-between;
  align-items: center;

  &:hover {
    background-color: #687078;
  }

  &:focus {
    border-color: ${AWS_BORDER_COLOR};
    box-shadow: unset;
  }
`;