import type { CSSProperties, PointerEvent } from "react";
import type { Privacy, VisualState } from "../state/visual";

interface Props {
  state: VisualState;
  level: number;
  badge: boolean;
  muted: boolean;
  privacy: Privacy;
  storageDegraded: boolean;
  onPointerDown: (e: PointerEvent<HTMLElement>) => void;
  onPointerMove: (e: PointerEvent<HTMLElement>) => void;
  onPointerUp: (e: PointerEvent<HTMLElement>) => void;
  onContextMenu: (e: React.MouseEvent) => void;
}

/** Original neon-blue orb. Pure presentation: state in, pixels out. */
export function Orb(p: Props) {
  const style = { "--level": p.level.toFixed(3) } as CSSProperties;
  return (
    <div className="orb-root" data-state={p.state} data-muted={p.muted} style={style}>
      <div className="orb-halo" />
      <div className="orb-wave w1" />
      <div className="orb-wave w2" />
      <div className="orb-wave w3" />
      <div className="orb-ring ring-a" />
      <div className="orb-ring ring-b" />
      <div className="orb-exec" />
      <div className="orb-ripple" />
      <button
        className="orb-core"
        aria-label={`JARVIS: ${p.state}`}
        onPointerDown={p.onPointerDown}
        onPointerMove={p.onPointerMove}
        onPointerUp={p.onPointerUp}
        onContextMenu={p.onContextMenu}
      >
        <span className="orb-shine" />
      </button>
      {p.badge && <span className="orb-badge" title="Há algo para você" />}
      {p.privacy.microphone && <span className="orb-dot dot-mic" title="Microfone ativo" />}
      {p.privacy.camera && <span className="orb-dot dot-cam" title="Câmera ativa" />}
      {p.storageDegraded && <span className="orb-dot dot-storage" title="Armazenamento externo indisponível" />}
    </div>
  );
}
