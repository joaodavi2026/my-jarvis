//! Pure geometry for the orb window (no Tauri types, fully unit-testable).
//! All values are physical pixels.

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
pub enum Corner {
    TopLeft,
    TopRight,
    BottomLeft,
    #[default]
    BottomRight,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
}

impl Rect {
    pub fn new(x: i32, y: i32, w: i32, h: i32) -> Self {
        Self { x, y, w, h }
    }
    fn right(&self) -> i32 {
        self.x + self.w
    }
    fn bottom(&self) -> i32 {
        self.y + self.h
    }
    fn contains(&self, px: i32, py: i32) -> bool {
        px >= self.x && px < self.right() && py >= self.y && py < self.bottom()
    }
}

/// Top-left position of a window of `size` whose visible orb (`core` px, centred in the
/// window) sits `margin` px away from the chosen corner of `area`.
pub fn corner_position(area: Rect, size: (i32, i32), core: i32, corner: Corner, margin: i32) -> (i32, i32) {
    let pad_x = (size.0 - core) / 2;
    let pad_y = (size.1 - core) / 2;
    let x = match corner {
        Corner::TopLeft | Corner::BottomLeft => area.x + margin - pad_x,
        Corner::TopRight | Corner::BottomRight => area.right() - margin - core - pad_x,
    };
    let y = match corner {
        Corner::TopLeft | Corner::TopRight => area.y + margin - pad_y,
        Corner::BottomLeft | Corner::BottomRight => area.bottom() - margin - core - pad_y,
    };
    (x, y)
}

/// A saved position is reused only if the window centre is still on some monitor
/// (the monitor may have been unplugged). The result is clamped fully inside that monitor.
pub fn visible_position(areas: &[Rect], pos: (i32, i32), size: (i32, i32)) -> Option<(i32, i32)> {
    let (cx, cy) = (pos.0 + size.0 / 2, pos.1 + size.1 / 2);
    let area = areas.iter().find(|a| a.contains(cx, cy))?;
    let x = pos.0.clamp(area.x, (area.right() - size.0).max(area.x));
    let y = pos.1.clamp(area.y, (area.bottom() - size.1).max(area.y));
    Some((x, y))
}

#[cfg(test)]
mod tests {
    use super::*;

    const AREA: Rect = Rect { x: 0, y: 0, w: 1920, h: 1040 };
    const SIZE: (i32, i32) = (160, 160);

    #[test]
    fn bottom_right_puts_the_orb_margin_px_from_the_corner() {
        let (x, y) = corner_position(AREA, SIZE, 64, Corner::BottomRight, 12);
        // visible orb spans [x+48, x+112]; its right edge must be 12px from the area edge
        assert_eq!(x + 48 + 64, 1920 - 12);
        assert_eq!(y + 48 + 64, 1040 - 12);
    }

    #[test]
    fn all_four_corners() {
        let tl = corner_position(AREA, SIZE, 64, Corner::TopLeft, 12);
        let tr = corner_position(AREA, SIZE, 64, Corner::TopRight, 12);
        let bl = corner_position(AREA, SIZE, 64, Corner::BottomLeft, 12);
        assert_eq!(tl, (12 - 48, 12 - 48));
        assert_eq!(tr.1, tl.1);
        assert_eq!(bl.0, tl.0);
        assert!(tr.0 > tl.0 && bl.1 > tl.1);
    }

    #[test]
    fn works_on_a_monitor_left_of_the_primary() {
        let left = Rect::new(-1920, 0, 1920, 1080);
        let (x, _) = corner_position(left, SIZE, 64, Corner::BottomRight, 12);
        assert!(x < 0 && x + 160 <= 0 + 48);
    }

    #[test]
    fn saved_position_is_kept_when_visible() {
        assert_eq!(visible_position(&[AREA], (500, 400), SIZE), Some((500, 400)));
    }

    #[test]
    fn saved_position_on_a_removed_monitor_is_rejected() {
        assert_eq!(visible_position(&[AREA], (-1700, 300), SIZE), None);
        assert_eq!(visible_position(&[], (10, 10), SIZE), None);
    }

    #[test]
    fn partially_off_screen_position_is_clamped_inside() {
        assert_eq!(visible_position(&[AREA], (1900, 1030), SIZE), Some((1760, 880)));
        assert_eq!(visible_position(&[AREA], (-60, -60), SIZE), Some((0, 0)));
    }

    #[test]
    fn corner_serialises_as_kebab_case() {
        assert_eq!(serde_json::to_string(&Corner::BottomRight).unwrap(), "\"bottom-right\"");
        assert_eq!(serde_json::from_str::<Corner>("\"top-left\"").unwrap(), Corner::TopLeft);
        assert!(serde_json::from_str::<Corner>("\"middle\"").is_err());
    }
}
