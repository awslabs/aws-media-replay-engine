import styled from "styled-components";
import { Link } from "react-router-dom";
import { BLACK, WHITE } from '@src/theme';

export const StyledHeader = styled.header`
    background-color: ${BLACK};
    height: 54px;
    padding: 0px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
`;

export const StyledLink = styled(Link)`
    display: flex;
    text-decoration: none;

    &:hover {
        span {
            color: #FACD5B;
        }
    }
`;

export const AWSLogo = styled.svg`
    height: 21px;
`;

export const AppTitle = styled.span`
    color: ${WHITE};
    font-size: 18px;
    margin-left: 22px;
`;

export const Divider = styled.div`
    height: 25px;
    background-color: ${WHITE};
    margin: 0px 10px;
    width: 1px;
`;