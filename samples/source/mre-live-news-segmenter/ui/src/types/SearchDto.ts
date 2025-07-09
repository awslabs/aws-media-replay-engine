export interface SearchDto {
  Summary: string;
  Details: Detail[];
}

export interface Detail {
  Title: string;
  Content: string;
  Start: number;
  End: number;
}
