export type SseEvent =
  | { type: 'token'; data: { delta: string } }
  | { type: 'citation'; data: { items: any[] } }
  | { type: 'done; data: any ' }
  | { type: 'error'; data: { message: string } }
  | { type: string; data: any };

export async function streamChat(
  apiUrl: string,
  payload: any,
  onEvent: (e: SseEvent) => void,
  signal?: AbortSignal
) {
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


  const reader = response.body?.getReader();
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
      let dataStr = "";
      for (const raw of frame.split(/\r?\n/)) {
        const line = raw.replace(/\r$/, "");

        if (line.startsWith("event:")) {
          event = line.slice(6).trim();
        } else if (line.startsWith("data")) {
          const payload = line.slice(5).replace(/^ /, "");
          dataStr += payload;
        }
      }

      // for (const line of frame.split("\n")) {
      //   if (line.startsWith("event:")) event = line.slice(6).trim();
      //   else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
      // }

      if (!dataStr) continue;
      onEvent({ event, data: JSON.parse(dataStr) } as SseEvent);
    }
  }
}


