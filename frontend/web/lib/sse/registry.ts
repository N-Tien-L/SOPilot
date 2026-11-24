// Open streams are tracked so a workspace switch can abort them all (R7).

const open = new Set<AbortController>();

/** Registers a stream; call the returned function when it ends. */
export function trackStream(controller: AbortController): () => void {
  open.add(controller);
  return () => {
    open.delete(controller);
  };
}

export function abortAllStreams(): void {
  for (const controller of [...open]) controller.abort();
  open.clear();
}

export function openStreamCount(): number {
  return open.size;
}
