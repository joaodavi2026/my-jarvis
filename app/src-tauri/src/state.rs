use crate::prefs::Prefs;
use std::{path::PathBuf, sync::atomic::AtomicU64, sync::Mutex};

/// Shell-owned state. The authoritative assistant state lives in the Python service.
pub struct AppState {
    pub prefs: Mutex<Prefs>,
    pub prefs_path: PathBuf,
    /// Incremented on every orb move; used to debounce saving the position.
    pub move_generation: AtomicU64,
}
