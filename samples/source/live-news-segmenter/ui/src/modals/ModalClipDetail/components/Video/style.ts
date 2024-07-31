import styled from "styled-components";
import { View } from "@aws-amplify/ui-react";

import { AWS_ORANGE } from "@src/theme";

export const VideoWrappper = styled(View)`
    position: absolute;
    width: 67%;
    height: 10px;
    bottom: 0;

    #end-marker {
      visibility: hidden;
      width: 5px;
      height: 20px;
      background: ${AWS_ORANGE};
      position: absolute;
      bottom: 12px;

      &:hover {
        visibility: visible !important;
      }
    }
`;

export const StyledVideo = styled.video`
    &:hover {
        & + div {
            #end-marker{
                visibility: visible !important;
            }
        }
    }
`;