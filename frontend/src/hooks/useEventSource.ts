import { startTransition, useEffect, useEffectEvent, useRef, useState } from "react";

import { coerceFullState, emptyFullState, mergeFullState, type FullState } from "../api/client";

type StreamStatus = "connecting" | "live" | "reconnecting" | "error";

type EventSourceLike = {
  addEventListener: (type: string, listener: EventListenerOrEventListenerObject) => void;
  removeEventListener: (type: string, listener: EventListenerOrEventListenerObject) => void;
  close: () => void;
  onerror: ((event: Event) => void) | null;
};

type EventSourceFactory = (url: string) => EventSourceLike;

function defaultEventSourceFactory(url: string): EventSourceLike {
  return new EventSource(url);
}

function parsePayload(payload: string): Partial<FullState> | null {
  try {
    return JSON.parse(payload) as Partial<FullState>;
  } catch {
    return null;
  }
}

export function useEventSource(url: string, createEventSource: EventSourceFactory = defaultEventSourceFactory) {
  const [state, setState] = useState<FullState>(emptyFullState);
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("connecting");
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const hasReceivedFullState = useRef(false);

  const applyFullState = useEffectEvent((payload: string) => {
    const parsed = parsePayload(payload);

    if (!parsed) {
      setStreamStatus("error");
      setErrorMessage("Stream returned an unreadable full-state payload.");
      return;
    }

    hasReceivedFullState.current = true;
    setErrorMessage(null);
    setLastSyncAt(new Date().toISOString());
    setStreamStatus("live");
    startTransition(() => {
      setState(coerceFullState(parsed));
    });
  });

  const applyDelta = useEffectEvent((payload: string) => {
    const parsed = parsePayload(payload);

    if (!parsed) {
      setErrorMessage("A delta update could not be parsed.");
      return;
    }

    setLastSyncAt(new Date().toISOString());
    startTransition(() => {
      setState((current) => mergeFullState(current, parsed));
    });
  });

  const markConnectionIssue = useEffectEvent(() => {
    setStreamStatus(hasReceivedFullState.current ? "reconnecting" : "error");
  });

  useEffect(() => {
    const source = createEventSource(url);

    setStreamStatus("connecting");
    setErrorMessage(null);
    hasReceivedFullState.current = false;

    const onFullState = (event: Event) => {
      applyFullState((event as MessageEvent<string>).data);
    };

    const onDelta = (event: Event) => {
      applyDelta((event as MessageEvent<string>).data);
    };

    const onError = () => {
      markConnectionIssue();
    };

    source.addEventListener("full_state", onFullState);
    source.addEventListener("delta", onDelta);
    source.onerror = onError;

    return () => {
      source.removeEventListener("full_state", onFullState);
      source.removeEventListener("delta", onDelta);
      source.close();
    };
  }, [createEventSource, url]);

  return {
    state,
    streamStatus,
    lastSyncAt,
    errorMessage,
  };
}
