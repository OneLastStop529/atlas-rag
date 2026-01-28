
export type SseEvent = { event: string; data: unknown };

export async function streamChat(
  apiUrl: string,
  payload: Record<string, unknown>,
  onEvent: (e: SseEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${apiUrl}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  if (!response.body) throw new Error('No response body');

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      let event = "message";
      const dataLines: string[] = [];

      for (const rawLine of frame.split(/\r?\n/)) {
        const line = rawLine.replace(/\r$/, "");
        if (line.startsWith("event:")) {
          event = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim());
        }
      }

      if (dataLines.length === 0) continue;
      const dataStr = dataLines.join("\n");

      try {
        onEvent({ event, data: JSON.parse(dataStr) });
      } catch (e) {
        console.error("Failed to parse SSE data:", e);
        onEvent({ event, data: dataStr });
      }
    }
  }
}


