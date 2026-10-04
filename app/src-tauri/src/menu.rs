//! Native menus (orb context menu and tray) and their actions. Menu ids are the contract with the UI.

use crate::placement::Corner;
use crate::windows;
use tauri::menu::{Menu, MenuBuilder, MenuEvent, MenuItemBuilder, SubmenuBuilder};
use tauri::{AppHandle, Emitter, Runtime};

pub fn orb_menu<R: Runtime>(app: &AppHandle<R>) -> tauri::Result<Menu<R>> {
    let position = SubmenuBuilder::new(app, "Posição do orbe")
        .text("corner:top-left", "Superior esquerdo")
        .text("corner:top-right", "Superior direito")
        .text("corner:bottom-left", "Inferior esquerdo")
        .text("corner:bottom-right", "Inferior direito")
        .build()?;
    MenuBuilder::new(app)
        .item(&MenuItemBuilder::with_id("activate", "Ativar JARVIS").build(app)?)
        .item(&MenuItemBuilder::with_id("mute", "Silenciar").build(app)?)
        .separator()
        .item(&MenuItemBuilder::with_id("open_panel", "Abrir painel").build(app)?)
        .item(&MenuItemBuilder::with_id("settings", "Configurações").build(app)?)
        .item(&MenuItemBuilder::with_id("history", "Histórico").build(app)?)
        .separator()
        .item(&MenuItemBuilder::with_id("microphone", "Microfone").build(app)?)
        .item(&MenuItemBuilder::with_id("camera", "Câmera").build(app)?)
        .item(&MenuItemBuilder::with_id("privacy", "Privacidade").build(app)?)
        .separator()
        .item(&position)
        .item(&MenuItemBuilder::with_id("simulator", "Simulador de estados (dev)").build(app)?)
        .item(&MenuItemBuilder::with_id("restart_service", "Reiniciar serviço").build(app)?)
        .separator()
        .item(&MenuItemBuilder::with_id("quit", "Sair").build(app)?)
        .build()
}

pub fn tray_menu<R: Runtime>(app: &AppHandle<R>) -> tauri::Result<Menu<R>> {
    MenuBuilder::new(app)
        .item(&MenuItemBuilder::with_id("open_panel", "Abrir JARVIS").build(app)?)
        .item(&MenuItemBuilder::with_id("activate", "Ativar").build(app)?)
        .item(&MenuItemBuilder::with_id("mute", "Silenciar").build(app)?)
        .item(&MenuItemBuilder::with_id("settings", "Configurações").build(app)?)
        .separator()
        .item(&MenuItemBuilder::with_id("restart_service", "Reiniciar").build(app)?)
        .item(&MenuItemBuilder::with_id("quit", "Sair").build(app)?)
        .build()
}

pub fn parse_corner(id: &str) -> Option<Corner> {
    match id.strip_prefix("corner:")? {
        "top-left" => Some(Corner::TopLeft),
        "top-right" => Some(Corner::TopRight),
        "bottom-left" => Some(Corner::BottomLeft),
        "bottom-right" => Some(Corner::BottomRight),
        _ => None,
    }
}

/// Window-level actions are handled here; everything else is forwarded to the orb UI.
pub fn handle_menu_event(app: &AppHandle, event: MenuEvent) {
    let id = event.id().as_ref();
    if let Some(corner) = parse_corner(id) {
        windows::set_corner(app, corner);
        return;
    }
    match id {
        "quit" => app.exit(0),
        "open_panel" | "settings" | "history" | "microphone" | "camera" | "privacy" => windows::show_panel(app),
        other => {
            // Includes restart_service: the service supervisor arrives in Phase 5.
            let _ = app.emit_to("orb", "jarvis://menu", other);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_corner_ids() {
        assert_eq!(parse_corner("corner:top-left"), Some(Corner::TopLeft));
        assert_eq!(parse_corner("corner:bottom-right"), Some(Corner::BottomRight));
        assert_eq!(parse_corner("corner:middle"), None);
        assert_eq!(parse_corner("quit"), None);
    }
}
