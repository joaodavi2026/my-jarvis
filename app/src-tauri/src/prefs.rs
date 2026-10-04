//! Window preferences owned by the shell (orb corner and position). Stored on the internal drive.
//! These are UI preferences only; no secrets and no user data.

use crate::placement::Corner;
use serde::{Deserialize, Serialize};
use std::{fs, io, path::Path};

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct Prefs {
    pub orb_corner: Corner,
    pub orb_position: Option<(i32, i32)>,
}

/// Missing file -> defaults. Corrupt file -> defaults, and the broken file is kept aside.
pub fn load(path: &Path) -> Prefs {
    let Ok(text) = fs::read_to_string(path) else {
        return Prefs::default();
    };
    match serde_json::from_str(&text) {
        Ok(prefs) => prefs,
        Err(_) => {
            let _ = fs::rename(path, path.with_extension("json.corrupt"));
            Prefs::default()
        }
    }
}

/// Atomic save: write a temporary file next to the target, then rename over it.
pub fn save(path: &Path, prefs: &Prefs) -> io::Result<()> {
    if let Some(dir) = path.parent() {
        fs::create_dir_all(dir)?;
    }
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, serde_json::to_vec_pretty(prefs)?)?;
    fs::rename(&tmp, path)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dir() -> std::path::PathBuf {
        let d = std::env::temp_dir().join(format!("jarvis-prefs-{}-{:?}", std::process::id(), std::thread::current().id()));
        let _ = fs::remove_dir_all(&d);
        fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn missing_file_gives_defaults() {
        let d = dir();
        assert_eq!(load(&d.join("prefs.json")), Prefs::default());
        assert_eq!(Prefs::default().orb_corner, Corner::BottomRight);
    }

    #[test]
    fn roundtrip() {
        let d = dir();
        let p = Prefs { orb_corner: Corner::TopLeft, orb_position: Some((10, -20)) };
        save(&d.join("prefs.json"), &p).unwrap();
        assert_eq!(load(&d.join("prefs.json")), p);
        assert!(!d.join("prefs.json.tmp").exists());
    }

    #[test]
    fn corrupt_file_is_set_aside_not_deleted() {
        let d = dir();
        fs::write(d.join("prefs.json"), "{nope").unwrap();
        assert_eq!(load(&d.join("prefs.json")), Prefs::default());
        assert!(d.join("prefs.json.corrupt").exists());
    }

    #[test]
    fn invalid_corner_value_falls_back_to_defaults() {
        let d = dir();
        fs::write(d.join("prefs.json"), r#"{"orb_corner":"middle"}"#).unwrap();
        assert_eq!(load(&d.join("prefs.json")).orb_corner, Corner::BottomRight);
    }

    #[test]
    fn unknown_fields_and_partial_files_are_tolerated() {
        let d = dir();
        fs::write(d.join("prefs.json"), r#"{"orb_position":[5,6],"future":true}"#).unwrap();
        assert_eq!(load(&d.join("prefs.json")).orb_position, Some((5, 6)));
    }
}
