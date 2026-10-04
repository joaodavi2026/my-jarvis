//! JARVIS desktop shell: lifecycle, tray, orb/panel windows. No assistant logic lives here.

mod commands;
mod menu;
mod placement;
mod prefs;
mod state;
mod windows;

use state::AppState;
use std::sync::{atomic::AtomicU64, Mutex};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Manager, RunEvent, WindowEvent};

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            // A second launch just brings the existing instance forward.
            windows::place_and_show_orb(app);
        }))
        .invoke_handler(tauri::generate_handler![
            commands::show_orb_menu,
            commands::open_panel,
            commands::send_to_service
        ])
        .on_menu_event(menu::handle_menu_event)
        .on_window_event(|window, event| match (window.label(), event) {
            // Closing the panel hides it; JARVIS keeps running in the background.
            ("panel", WindowEvent::CloseRequested { api, .. }) => {
                api.prevent_close();
                let _ = window.hide();
            }
            ("orb", WindowEvent::Moved(pos)) => windows::on_orb_moved(window.app_handle(), *pos),
            _ => {}
        })
        .setup(|app| {
            let prefs_path = app.path().app_config_dir()?.join("shell-prefs.json");
            app.manage(AppState {
                prefs: Mutex::new(prefs::load(&prefs_path)),
                prefs_path,
                move_generation: AtomicU64::new(0),
            });

            let tray_menu = menu::tray_menu(app.handle())?;
            let mut tray = TrayIconBuilder::with_id("main")
                .tooltip("JARVIS")
                .menu(&tray_menu)
                .show_menu_on_left_click(false)
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                        windows::show_panel(tray.app_handle());
                    }
                });
            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            tray.build(app)?;

            windows::place_and_show_orb(app.handle());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build the JARVIS shell");

    app.run(|_app, event| {
        // Only an explicit Quit (tray or menu) ends the app; closing windows never does.
        if let RunEvent::ExitRequested { api, code, .. } = event {
            if code.is_none() {
                api.prevent_exit();
            }
        }
    });
}
