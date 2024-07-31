import { Flex, Text } from '@aws-amplify/ui-react';
import { Tag } from 'antd';
import styled from 'styled-components';

import { WHITE } from '@src/theme';

const StyledTag = styled(Tag)`
  background: #d13212;
  padding: 6px 27px 6px 12px;
  border: unset;
  border-radius: 16px;
  color: ${WHITE};
  position: absolute;
  top: 17px;
  right: 10px;
`;

export const LiveNowTag = () => {
  return (
    <StyledTag>
      <Flex justifyContent="center" gap={15}>
        <svg width="20" height="20" xmlns="http://www.w3.org/2000/svg">
          <circle
            cx="10"
            cy="10"
            r="8"
            fill="none"
            stroke={WHITE}
            strokeWidth="2"
          >
            <animate
              attributeName="r"
              values="6;8;6"
              dur="1s"
              repeatCount="indefinite"
            />
            <animate
              attributeName="stroke-width"
              values="1;2;1"
              dur="1s"
              repeatCount="indefinite"
            />
          </circle>
          <circle cx="10" cy="10" r="4" fill={WHITE}></circle>
        </svg>
        <Text as="span" fontSize={14} fontWeight={700}>
          Live Now
        </Text>
      </Flex>
    </StyledTag>
  );
};
