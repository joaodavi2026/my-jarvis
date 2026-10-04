use crate::placement::{corner_position, visible_position, Corner, Rect};
use crate::prefs;
use crate::state::AppState;
use std::{sync::atomic::Ordering, time::Duration};
use tauri::{AppHandle, Manager, PhysicalPosition, WebviewWindow};

const ORB_CORE_PX: f64 = 64.0;
const MARGIN_PX: f64 = 12.0;
const SAVE_DEBOUNCE: Duration = Duration::from_millis(600);

fn rect_of(monitor: &tauri::Monitor) -> Rect {
    let wa = monitor.work_area();
    Rect::new(wa.position.x, wa.position.y, wa.size.width as i32, wa.size.height as i32)
}

fn work_areas(window: &WebviewWindow) -> Vec<Rect> {
    window.available_monitors().unwrap_or_default().iter().map(rect_of).collect()
}

fn primary_area(window: &WebviewWindow) -> Option<Rect> {
    let monitor = window.primary_monitor().ok().flatten().or_else(|| window.current_monitor().ok().flatten())?;
    Some(rect_of(&monitor))
}

/// Positions the orb (saved position if still visible, otherwise the configured corner) and shows it.
pub fn place_and_show_orb(app: &AppHandle) {
    let Some(orb) = app.get_webview_window("orb") else { return };
    let state = app.state::<AppState>();
    let prefs = state.prefs.lock().unwrap().clone();
    let scale = orb.scale_factor().unwrap_or(1.0);
    let size = orb.outer_size().map(|s| (s.width as i32, s.height as i32)).unwrap_or((160, 160));

    let saved = prefs.orb_position.and_then(|p| visible_position(&work_areas(&orb), p, size));
    let position = saved.or_else(|| {
        primary_area(&orb).map(|area| {
            corner_position(area, size, (ORB_CORE_PX * scale) as i32, prefs.orb_corner, (MARGIN_PX * scale) as i32)
        })
    });
    if let Some((x, y)) = position {
        let _ = orb.set_position(PhysicalPosition::new(x, y));
    }
    let _ = orb.show();
}

/// User picked a corner from the menu: move there and forget the free-drag position.
pub fn set_corner(app: &AppHandle, corner: Corner) {
    {
        let state = app.state::<AppState>();
        let mut prefs = state.prefs.lock().unwrap();
        prefs.orb_corner = corner;
        prefs.orb_position = None;
        let _ = prefs::save(&state.prefs_path, &prefs);
    }
    place_and_show_orb(app);
}

/// Called on every move of the orb window; saves once the drag has settled.
pub fn on_orb_moved(app: &AppHandle, pos: PhysicalPosition<i32>) {
    let state = app.state::<AppState>();
    let generation = state.move_generation.fetch_add(1, Ordering::SeqCst) + 1;
    let app = app.clone();
    std::thread::spawn(move || {
        std::thread::sleep(SAVE_DEBOUNCE);
        let state = app.state::<AppState>();
        if state.move_generation.load(Ordering::SeqCst) != generation {
            return;
        }
        let mut prefs = state.prefs.lock().unwrap();
        prefs.orb_position = Some((pos.x, pos.y));
        let _ = prefs::save(&state.prefs_path, &prefs);
    });
}

pub fn show_panel(app: &AppHandle) {
    if let Some(panel) = app.get_webview_window("panel") {
        let _ = panel.show();
        let _ = panel.unminimize();
        let _ = panel.set_focus();
    }
}
