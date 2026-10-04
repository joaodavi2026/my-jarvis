// Menu templates. The menu ids are the contract with the UI and with main.ts.
import type { MenuItemConstructorOptions } from "electron";

export const CORNER_ITEMS: { id: string; label: string }[] = [
  { id: "corner:top-left", label: "Superior esquerdo" },
  { id: "corner:top-right", label: "Superior direito" },
  { id: "corner:bottom-left", label: "Inferior esquerdo" },
  { id: "corner:bottom-right", label: "Inferior direito" },
];

type Click = (id: string) => void;

export function orbMenuTemplate(onAction: Click, muted: boolean): MenuItemConstructorOptions[] {
  const item = (id: string, label: string): MenuItemConstructorOptions => ({ label, click: () => onAction(id) });
  return [
    item("activate", "Ativar JARVIS"),
    item("mute", muted ? "Reativar" : "Silenciar"),
    { type: "separator" },
    item("open_panel", "Abrir painel"),
    item("settings", "Configurações"),
    item("history", "Histórico"),
    { type: "separator" },
    item("microphone", "Microfone"),
    item("camera", "Câmera"),
    item("privacy", "Privacidade"),
    { type: "separator" },
    { label: "Posição do orbe", submenu: CORNER_ITEMS.map((c) => item(c.id, c.label)) },
    item("simulator", "Simulador de estados (dev)"),
    item("restart_service", "Reiniciar serviço"),
    { type: "separator" },
    item("quit", "Sair"),
  ];
}

export function trayMenuTemplate(onAction: Click): MenuItemConstructorOptions[] {
  const item = (id: string, label: string): MenuItemConstructorOptions => ({ label, click: () => onAction(id) });
  return [
    item("open_panel", "Abrir JARVIS"),
    item("activate", "Ativar"),
    item("mute", "Silenciar"),
    item("settings", "Configurações"),
    { type: "separator" },
    item("restart_service", "Reiniciar"),
    item("quit", "Sair"),
  ];
}
