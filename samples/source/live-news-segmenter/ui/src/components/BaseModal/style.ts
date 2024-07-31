import Rodal from 'rodal';
import styled from "styled-components";
import { Flex, View } from '@aws-amplify/ui-react';

import { AWS_DARK, AWS_CLOSE_ICON_COLOR } from '@src/theme';

export const Modal = styled(Rodal)`
    .rodal-mask {
        background-color: rgba(0,0,0,0.6);
    }

    .rodal-dialog {
        background-color: ${AWS_DARK};
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 2px 4px 0 rgba(0,0,0,0.50);
        display: flex;
        flex-direction: column;
        position: relative;
        top: 50%;
        transform: translateY(-50%);
    }

    .rodal-close {
        display: none;
    }
`;

export const Header = styled(Flex)`
    .header-title {
        font-size: 20px;
        font-weight: 700;
    }

    .header-btn-close {
        color: ${AWS_CLOSE_ICON_COLOR};
        cursor: pointer;
    }
`;

export const Content = styled(View)`
    flex: 1;
    margin: 0px 0 20px 0;
`;

export const Footer = styled(Flex)`
    button {
        font-size: 12px;;
    }
`;