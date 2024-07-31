import { Accordion, Flex, Loader, Text } from '@aws-amplify/ui-react';
import { faCaretDown, faCaretUp } from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { FC, ReactNode, useCallback, useState } from 'react';

import { StyledAccordion, StyledTrigger } from './style';

import { AWS_BORDER_COLOR, WHITE } from '@src/theme';
import { AccordionItem } from '@src/types';

interface BaseAccordionProps {
  items: AccordionItem[];
  // Use this to get dynamic content from the server
  // Once this is set, "content" prop in each item will be ignored
  getContent?: (value: string) => Promise<{
    success: boolean;
    contents?: ReactNode[];
  }>;
  onTriggerClick?: (value?: string) => void;
}

interface Content {
  [key: string]: {
    loading: boolean;
    contents?: ReactNode[];
  };
}

export const BaseAccordion: FC<BaseAccordionProps> = ({
  items,
  getContent,
  onTriggerClick,
}) => {
  const [contentList, setContentList] = useState<Content>({});
  const handleTriggerClick = async (value: string) => {
    if (getContent) {
      const content: Content = {
        [value]: {
          loading: true,
        },
      };
      setContentList({
        ...contentList,
        ...content,
      });

      const data = await getContent(value);
      if (data.success) {
        content[value].loading = false;
        content[value].contents = data.contents;
      }
      setContentList({
        ...contentList,
        ...content,
      });
    }
    if (onTriggerClick) {
      onTriggerClick(value);
    }
  };

  const setAccordionContent = useCallback(
    (item: AccordionItem) => {
      if (!getContent) return item.content;
      return contentList[item.value] && contentList[item.value].contents
        ? (contentList[item.value].contents as ReactNode)
        : null;
    },
    [contentList, getContent],
  );

  return (
    <StyledAccordion allowMultiple>
      {items.map((item) => (
        <Accordion.Item value={item.value} key={item.value}>
          <StyledTrigger onClick={() => handleTriggerClick(item.value)}>
            <Flex gap={34}>
              <FontAwesomeIcon icon={faCaretDown} />
              <FontAwesomeIcon icon={faCaretUp} />
              <Text lineHeight={1}>{item.heading}</Text>
            </Flex>
            <Loader
              filledColor={WHITE}
              emptyColor={AWS_BORDER_COLOR}
              className={`icon--loader ${contentList[item.value] && contentList[item.value].loading ? 'is--loading' : ''}`}
            />
          </StyledTrigger>
          <Accordion.Content>{setAccordionContent(item)}</Accordion.Content>
        </Accordion.Item>
      ))}
    </StyledAccordion>
  );
};
