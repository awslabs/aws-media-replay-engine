import { useContext, createContext } from "react";
import { ContentViews, SortOrders } from "@src/enums";
import { ChildThemeDto } from '@src/types';

interface NewsPageProps {
    setContentView: (contentView: ContentViews) => void;
    sortOrder: SortOrders;
    setSortOrder: (sortOrder: SortOrders) => void;
    followTopics: ChildThemeDto[];
    setFollowTopics: (followTopics: ChildThemeDto[], resetting?: boolean) => void;
    currentSegment: ChildThemeDto;
    setCurrentSegment: (currentSegment: ChildThemeDto) => void;
    searchPanelVisibility: boolean;
    setSearchPanelVisibility: (searchPanelVisibility: boolean) => void;
    searchResults: ChildThemeDto[];
    setSearchResults: (searchResults: ChildThemeDto[]) => void;
    currentPlayedVideo: HTMLVideoElement | null;
    setCurrentPlayedVideo: (currentPlayedVideo: HTMLVideoElement) => void;
    height: number;
    videoLink: string;
}

export const NewsPageContext = createContext({} as NewsPageProps);

export function useNewsPageContext() {
    return useContext(NewsPageContext);
}