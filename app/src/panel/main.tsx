import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { bridge } from "../ipc/bridge";
import { useAppModel } from "../state/hooks";
import type { FlowName } from "../state/sim";
import { deriveVisual } from "../state/visual";
import type { VisualState } from "../state/visual";
import "../styles.css";
import "./panel.css";

const VISUALS: VisualState[] = ["IDLE", "LISTENING", "THINKING", "EXECUTING", "AWAITING", "SPEAKING", "SUCCESS", "ERROR", "OFFLINE"];
const TRIGGER_FOR: Record<string, string[]> = {
  IDLE: [],
  LISTENING: ["activation_requested", "listening_started"],
  THINKING: ["activation_requested", "listening_started", "transcription_ready"],
  EXECUTING: ["activation_requested", "listening_started", "transcription_ready", "tool_started"],
  AWAITING: ["activation_requested", "listening_started", "transcription_ready", "confirmation_requested"],
  SPEAKING: ["activation_requested", "listening_started", "transcription_ready", "response_ready"],
};

function PanelApp() {
  const [model, dispatch] = useAppModel();
  const visual = deriveVisual(model);
  const simulated = model.source === "simulated";
  // The panel and the orb are separate windows: actions are broadcast so both reduce the same stream.
  const act = (a: Parameters<typeof dispatch>[0]) => {
    dispatch(a);
    bridge.broadcastAction(a);
  };
  const goto = (target: VisualState) => {
    act({ type: "source", source: "simulated" });
    if (target === "SUCCESS" || target === "ERROR") return act({ type: "pulse", pulse: target });
    if (target === "OFFLINE") return act({ type: "trigger", trigger: "service_lost" });
    act({ type: "source", source: "simulated" });
    for (const t of TRIGGER_FOR[target] ?? []) act({ type: "trigger", trigger: t });
  };

  return (
    <main className="panel">
      <header>
        <h1>JARVIS</h1>
        <span className="state" data-state={visual}>{visual}</span>
      </header>

      <section>
        <h2>Serviços</h2>
        <ul className="rows">
          <li><span>Serviço local</span><b>{simulated ? "SIMULADO" : model.service}</b></li>
          <li><span>Armazenamento externo</span><b>{model.storageDegraded ? "INDISPONÍVEL" : "—"}</b></li>
          <li><span>Microfone</span><b>{model.privacy.microphone ? "ATIVO" : "inativo"}</b></li>
          <li><span>Câmera</span><b>{model.privacy.camera ? "ATIVA" : "inativa"}</b></li>
          <li><span>Nuvem</span><b>{model.privacy.cloud ? "EM USO" : "desligada"}</b></li>
        </ul>
      </section>

      <section>
        <h2>Simulador de estados (desenvolvimento)</h2>
        <p className="hint">Mostra os estados visuais do orbe antes de o serviço Python existir. Não envia comandos reais.</p>
        <div className="grid">
          <button onClick={() => act({ type: "source", source: simulated ? "service" : "simulated" })}>
            {simulated ? "Desligar simulador" : "Ligar simulador"}
          </button>
        </div>
        {simulated && (
          <>
            <div className="grid">
              {VISUALS.map((v) => (
                <button key={v} className={v === visual ? "on" : ""} onClick={() => goto(v)}>{v}</button>
              ))}
            </div>
            <h2>Fluxos</h2>
            <div className="grid">
              {(["voice", "tool", "confirm", "briefing", "error"] as FlowName[]).map((f) => (
                <button key={f} onClick={() => bridge.broadcastAction({ type: "trigger", trigger: `__flow:${f}` })}>
                  {f}
                </button>
              ))}
            </div>
          </>
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PanelApp />
  </StrictMode>,
);
