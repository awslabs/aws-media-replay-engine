import { ReactNode } from 'react';

export interface AccordionItem {
  heading: ReactNode;
  value: string;
  content: ReactNode;
}
