import { Loader, View } from '@aws-amplify/ui-react';
import styled from 'styled-components';

import { AWS_ORANGE } from '@src/theme';

const StyledLoader = styled(Loader)`
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100px;
`;

const Container = styled(View)`
  position: absolute;
  width: 100vw;
  height: 100vh;
  background-color: rgba(255, 255, 255, 0.5);
`;

export const BaseLoader = () => {
  return (
    <Container>
      <StyledLoader filledColor={AWS_ORANGE} />
    </Container>
  );
};
