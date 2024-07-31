import { View } from '@aws-amplify/ui-react';
import styled from 'styled-components';

import {
    AWS_CLOSE_ICON_COLOR,
    AWS_DARKER,
    BLACK,
    AWS_BORDER_COLOR,
} from '@src/theme';

export const StyleView = styled(View)`
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: ${AWS_DARKER};
  padding: 15px 25px 85px 25px;
  animation-duration: 0.5s !important;
  z-index: 1;

  .btn--close {
    position: absolute;
    top: 15px;
    right: 20px;
    font-size: 12px;
    cursor: pointer;

        svg {
        fill: ${AWS_CLOSE_ICON_COLOR};
        }
    }

    .from--me, .from--bot {
        background: ${AWS_BORDER_COLOR};
        border-radius: 12px;
        padding: 11px;
        margin-bottom: 14px;
        font-size: 14px;
        font-weight: 400;
    }

    .from--bot {
        background: ${BLACK};
    }

    .input__search {
        position: absolute;
        bottom: 15px;
        width: calc(100% - 50px);
        left: 50%;
        transform: translateX(-50%);

        input {
            background-color: ${BLACK};
            border: 0.5px solid ${AWS_BORDER_COLOR};
            box-shadow: 0 2px 4px 0 rgba(0,0,0,0.50);
            border-radius: 10px;
            padding: 16px 66px 16px 16px;
        }

        button {
            border-radius: 50%;
            width: 28px;
            height: 34px;
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            right: 16px;
            font-size: 14px;
        }
    }
`;