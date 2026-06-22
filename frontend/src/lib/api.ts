import { StageEvent } from "@/types/research";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Streams pipeline progress via Server-Sent Events.
 * Calling code provides an onStage callback fired for every stage event,
 * and onComplete/onError for terminal states.
 */
export async function streamResearch(
  topic: string,
  onStage: (event: StageEvent) => void,
  onComplete: () => void,
  onError: (message: string) => void
) {
  try {
    const response = await fetch(`${API_BASE}/api/research/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    });

    if (!response.ok || !response.body) {
      onError(`Request failed: ${response.status}`);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by a blank line.
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const raw of events) {
        const eventLine = raw.split("\n").find((l) => l.startsWith("event:"));
        const dataLine = raw.split("\n").find((l) => l.startsWith("data:"));
        if (!dataLine) continue;

        const eventType = eventLine?.replace("event:", "").trim();
        const data = JSON.parse(dataLine.replace("data:", "").trim());

        if (eventType === "complete") {
          onComplete();
        } else if (eventType === "error") {
          onError(data.message || "The research pipeline failed.");
        } else {
          onStage(data as StageEvent);
        }
      }
    }
  } catch (err) {
    onError(err instanceof Error ? err.message : "Unknown streaming error");
  }
}
