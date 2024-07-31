import { SearchOutlined } from '@ant-design/icons';
import { Flex, View } from '@aws-amplify/ui-react';
import { faArrowsRotate, faCaretDown } from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { Tooltip } from 'antd';
import { FC, ReactNode, useEffect, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

import { ButtonGroup, SearchButton } from './style';

import {
  BaseAccordion,
  BaseLink,
  BaseScrollableContent,
  BaseSegment,
  BaseSelectField,
} from '@src/components';
import { useNewsPageContext, useSessionContext } from '@src/contexts';
import { ContentViews, EventStatuses, SortOrders } from '@src/enums';
import { services } from '@src/services';
import { AWS_BORDER_COLOR, AWS_ORANGE } from '@src/theme';
import { AccordionItem, ChildThemeDto } from '@src/types';

interface ContentsProps {
  contentView: ContentViews;
  segments: ChildThemeDto[];
  onRefresh: (sortOrder?: SortOrders) => void;
  isLoading: boolean;
  isLoadingFollowTopics: boolean;
}

export const Contents: FC<ContentsProps> = ({
  contentView,
  segments,
  onRefresh,
  isLoading,
  isLoadingFollowTopics,
}) => {
  const {
    setContentView,
    setSortOrder,
    sortOrder,
    searchResults,
    setSearchResults,
    searchPanelVisibility,
    setSearchPanelVisibility,
    height,
  } = useNewsPageContext();

  const { event } = useSessionContext();

  const [accordionItems, setAccordionItems] = useState<AccordionItem[]>([]);

  useEffect(() => {
    if (contentView === ContentViews.THEME) {
      setAccordionItems(
        segments.map((theme) => ({
          heading: theme.Label,
          value: theme.Start,
          content: null,
        })),
      );
    } else {
      setAccordionItems([]);
    }
  }, [contentView, segments]);

  const handleGetContent = (value: string) => {
    return new Promise<{
      success: boolean;
      contents?: ReactNode[];
    }>((resolve) => {
      const theme = segments.find((segment) => segment.Start === value);
      if (!theme) {
        resolve({ success: false });
        return;
      }
      services
        .getChildThemes({
          program: theme.Program,
          event: theme.Event,
          plugin_name: theme.PluginName,
          start: theme.Start,
          end: theme.End,
        })
        .then((response) => {
          if (response.success) {
            const contents = response.data.map((childTheme) => (
              <BaseSegment key={uuidv4()} segment={childTheme} className="" />
            ));
            resolve({ success: true, contents });
          } else {
            resolve({ success: false });
          }
        });
    });
  };

  const handleSortOrderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const _sortOrder = e.target.value as SortOrders;
    setSortOrder(_sortOrder);
    onRefresh(_sortOrder);
  };

  const buildBaseSegments = (segments: ChildThemeDto[]) =>
    segments.map((segment, index) => (
      <BaseSegment
        key={segment.Start + segment.End}
        segment={segment}
        className={`position-${index + 1}`}
      />
    ));

  return (
    <View>
      {searchResults.length > 0 ? (
        <>
          <Flex
            padding={'17px 15.5px'}
            justifyContent="space-between"
            alignItems="center"
          >
            <span style={{ fontSize: 14 }}>
              Showing {searchResults.length} result
              {searchResults.length > 1 ? 's' : ''} from Search
            </span>
            <BaseLink
              onClick={(e) => {
                e.preventDefault();
                setSearchResults([]);
              }}
            >
              Clear Result{searchResults.length > 1 ? 's' : ''}
            </BaseLink>
          </Flex>
          <BaseScrollableContent height={height}>
            {buildBaseSegments(searchResults)}
          </BaseScrollableContent>
        </>
      ) : (
        <>
          <Flex padding={'17px 15.5px'} justifyContent="space-between">
            <Flex alignItems="center">
              <span style={{ fontSize: 14 }}>Content View</span>
              <ButtonGroup>
                <View
                  className={contentView === ContentViews.THEME ? 'active' : ''}
                  onClick={() => {
                    setContentView(ContentViews.THEME);
                  }}
                >
                  Theme
                </View>
                <View
                  className={contentView === ContentViews.TIME ? 'active' : ''}
                  onClick={() => {
                    setContentView(ContentViews.TIME);
                  }}
                >
                  Time
                </View>
              </ButtonGroup>
              <Tooltip title="Refresh" color={AWS_ORANGE}>
                <FontAwesomeIcon
                  icon={faArrowsRotate}
                  cursor={isLoading ? 'not-allowed' : 'pointer'}
                  onClick={() => onRefresh()}
                  color={isLoading ? AWS_BORDER_COLOR : undefined}
                />
              </Tooltip>
            </Flex>

            <Flex>
              {event.Status !== EventStatuses.QUEUED && (
                <SearchButton
                  variation="primary"
                  onClick={() =>
                    setSearchPanelVisibility(!searchPanelVisibility)
                  }
                  disabled={isLoadingFollowTopics}
                >
                  <SearchOutlined />
                  Search
                </SearchButton>
              )}

              <BaseSelectField
                labelHidden
                label=""
                value={sortOrder}
                icon={<FontAwesomeIcon icon={faCaretDown} />}
                onChange={handleSortOrderChange}
                disabled={isLoading}
                iconColor={
                  isLoading
                    ? 'var(--amplify-components-select-disabled-color)'
                    : undefined
                }
              >
                <option value={SortOrders.DESC}>Newest to Oldest</option>
                <option value={SortOrders.ASC}>Oldest to Newest</option>
              </BaseSelectField>
            </Flex>
          </Flex>
          {segments.length > 0 && (
            <BaseScrollableContent
              height={height}
              display={isLoading ? 'none' : 'block'}
            >
              {contentView === ContentViews.TIME ? (
                buildBaseSegments(segments)
              ) : (
                <BaseAccordion
                  items={accordionItems}
                  getContent={handleGetContent}
                />
              )}
            </BaseScrollableContent>
          )}
        </>
      )}
    </View>
  );
};
