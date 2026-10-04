import { StrictMode, useCallback, useEffect, useRef } from "react";
import type { PointerEvent } from "react";
import { createRoot } from "react-dom/client";
import { bridge } from "../ipc/bridge";
import { useAppModel } from "../state/hooks";
import { playFlow } from "../state/sim";
import { clickAction, deriveVisual } from "../state/visual";
import "../styles.css";
import "./orb.css";
import { isDrag } from "./gesture";
import type { PointerStart } from "./gesture";
import { Orb } from "./Orb";

function OrbApp() {
  const [model, dispatch] = useAppModel();
  const visual = deriveVisual(model);
  const flow = useRef<(() => void) | null>(null);
  const start = useRef<PointerStart | null>(null);
  const dragging = useRef(false);

  const stopFlow = () => {
    flow.current?.();
    flow.current = null;
  };

  const activate = useCallback(() => {
    if (model.source === "simulated") {
      stopFlow();
      flow.current = playFlow("voice", dispatch);
    } else {
      void bridge.send("activation.orb_clicked");
    }
  }, [model.source, dispatch]);

  const cancel = useCallback(() => {
    if (model.source === "simulated") {
      stopFlow();
      dispatch({ type: "trigger", trigger: "cancel_requested" });
      setTimeout(() => dispatch({ type: "trigger", trigger: "cancel_completed" }), 350);
    } else {
      void bridge.send("activation.cancelled", { source: "orb" });
    }
  }, [model.source, dispatch]);

  const perform = useCallback(
    (action: ReturnType<typeof clickAction>) => {
      if (action === "activate") activate();
      else if (action === "cancel") cancel();
      else if (action === "open_panel") void bridge.openPanel();
    },
    [activate, cancel],
  );

  useEffect(() => {
    let off: (() => void) | undefined;
    let disposed = false;
    bridge
      .onMenu((action) => {
        if (action === "activate") perform("activate");
        else if (action === "mute") dispatch({ type: "muted", muted: !model.muted });
        else if (action === "simulator") dispatch({ type: "source", source: model.source === "simulated" ? "service" : "simulated" });
      })
      .then((fn) => (disposed ? fn() : (off = fn)));
    return () => {
      disposed = true;
      off?.();
    };
  }, [perform, dispatch, model.muted, model.source]);

  const onPointerDown = (e: PointerEvent<HTMLElement>) => {
    if (e.button !== 0) return;
    start.current = { x: e.clientX, y: e.clientY };
    dragging.current = false;
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: PointerEvent<HTMLElement>) => {
    if (!start.current || dragging.current) return;
    if (isDrag(start.current, e.clientX, e.clientY)) {
      dragging.current = true;
      e.currentTarget.releasePointerCapture(e.pointerId);
      void bridge.startDragging();
    }
  };
  const onPointerUp = (e: PointerEvent<HTMLElement>) => {
    const wasClick = start.current !== null && !dragging.current && e.button === 0;
    start.current = null;
    if (wasClick) perform(clickAction(visual));
  };

  return (
    <Orb
      state={visual}
      level={model.level}
      badge={model.badge}
      muted={model.muted}
      privacy={model.privacy}
      storageDegraded={model.storageDegraded}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onContextMenu={(e) => {
        e.preventDefault();
        void bridge.showOrbMenu();
      }}
    />
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <OrbApp />
  </StrictMode>,
);
