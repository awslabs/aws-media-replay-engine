import { Detail } from '@src/types';

export function getChunksAsBytes(summaryStream: string) {
  const token = '{"chunk":{"bytes":{';
  const parts = summaryStream.split(token);

  const chunksAsBytes = [];
  for (const part of parts) {
    if (part.trim().length < 1) {
      continue;
    }
    chunksAsBytes.push(JSON.parse(`${token}${part}`));
  }

  return chunksAsBytes;
}

export const getSummary = (chunk: string) => {
  const match = chunk.match(/"Summary":\s*"([^"]*)|"/m);
  if (match) {
    return match[1];
  }
  return '';
};

export const getDetails = (chunk: string): Detail[] => {
  const match = chunk.match(/"Details":\s*\[(.*?)\]/s);
  if (match) {
    return JSON.parse(`[${match[1]}]`);
  }
  return [];
};

export const getTitles = (chunk: string): string[] => {
  const match = chunk.match(/"Title": "([^"]+)"/g);
  if (match) {
    const arr = match.map((title) =>
      title.replace('"Title": "', '').replace('"', ''),
    );
    const s = new Set(arr);
    const it = s.values();
    return Array.from(it);
  }
  return [];
};

export const getObjectsInDetails = (chunk: string): Detail[] => {
  const matchTitle = chunk.match(/"Title": "([^"]+)"/g);
  const matchContent = chunk.match(/"Content": "([^"]+)"/g);
  const matchStart = chunk.match(/"Start": ([0-9.]+)/g);
  const matchEnd = chunk.match(/"End": ([0-9.]+)/g);

  const extracted_objects = [];

  if (matchTitle && matchContent && matchStart && matchEnd) {
    for (let i = 0; i < matchTitle.length; i++) {
      if (matchTitle[i] && matchContent[i] && matchStart[i] && matchEnd[i]) {
        const title = matchTitle[i].replace('"Title": "', '').replace('"', '');
        const content = matchContent[i]
          .replace('"Content": "', '')
          .replace('"', '');
        const start = +matchStart[i].replace('"Start": ', '');
        const end = +matchEnd[i].replace('"End": ', '');
        extracted_objects.push({
          Title: title,
          Content: content,
          Start: start,
          End: end,
        });
      }
    }
  }

  return extracted_objects;
};
