use crate::{menu, windows};
use tauri::{AppHandle, WebviewWindow};

#[tauri::command]
pub fn show_orb_menu(app: AppHandle, window: WebviewWindow) -> Result<(), String> {
    let menu = menu::orb_menu(&app).map_err(|e| e.to_string())?;
    window.popup_menu(&menu).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn open_panel(app: AppHandle) {
    windows::show_panel(&app);
}

/// Forwards a message to the Python service. The service bridge arrives in Phase 5;
/// until then this fails explicitly instead of pretending to deliver.
#[tauri::command]
pub fn send_to_service(_message: serde_json::Value) -> Result<(), String> {
    Err("service_unavailable".into())
}
