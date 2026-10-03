// One line of Ollama's NDJSON chat stream. A partial or garbled line is skipped, not fatal: the rest of the stream is still good.
export function parseOllamaLine<T>(line: string): T | null {
  if (!line.trim()) return null;
  try {
    return JSON.parse(line) as T;
  } catch {
    return null;
  }
}
