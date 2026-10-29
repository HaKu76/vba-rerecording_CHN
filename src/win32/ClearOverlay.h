#ifndef VBA_WIN32_CLEAR_OVERLAY_H
#define VBA_WIN32_CLEAR_OVERLAY_H

// Straight-alpha BGRA, at three samples per LCD pixel. Display backends draw
// this after the game texture, using nearest-neighbor sampling independently.
const u32 *winPrepareClearOverlay(int &width, int &height);
bool winHasClearOverlay();
void winDrawClearOverlay(HDC dc, const RECT &destination);
void winCaptureClearOverlay(u8 *frame, int pitch);

#endif
