#ifndef VBA_LUA_WIN32_TEXT_H
#define VBA_LUA_WIN32_TEXT_H

// Kept independent of MFC so the UTF-8 decoder and glyph rasterizer can be
// compiled and exercised without starting the emulator. No locale/ACP fallback.
#include <windows.h>
#include <map>
#include <string>
#include <vector>
#include <climits>

namespace LuaWin32Text
{
inline bool LoadBundledFonts()
{
    // Private, process-lifetime registrations: no Windows font installation.
    struct Bundle
    {
        HANDLE handles[2];
        Bundle()
        {
            handles[0] = handles[1] = NULL;
            for (int i = 0; i < 2; ++i)
            {
                HMODULE module = GetModuleHandleW(NULL);
                HRSRC resource = FindResourceW(module, MAKEINTRESOURCEW(43530 + i), MAKEINTRESOURCEW(10));
                if (!resource) continue;
                HGLOBAL data = LoadResource(module, resource);
                void *bytes = data ? LockResource(data) : NULL;
                DWORD count = 0;
                if (bytes) handles[i] = AddFontMemResourceEx(bytes, SizeofResource(module, resource), NULL, &count);
            }
        }
    };
    static Bundle bundle;
    return bundle.handles[0] && bundle.handles[1];
}

inline bool DecodeUTF8(const char *text, size_t length, std::wstring &out)
{
    out.clear();
    if (!length)
        return true;
    if (length > INT_MAX)
        return false;
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text,
                                  (int)length, NULL, 0);
    if (!count)
        return false;
    out.resize(count);
    return MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text,
                              (int)length, &out[0], count) == count;
}

struct Glyph
{
    int width, height;
    std::vector<unsigned char> mask;
    Glyph() : width(0), height(0) {}

    bool ink(int x, int y) const
    {
        return x >= 0 && y >= 0 && x < width && y < height
            && mask[y * width + x] != 0;
    }
};

class Rasterizer
{
    HDC dc;
    HFONT font;
    HGDIOBJ oldFont;
    int size, lineHeight;
    std::wstring faceName;
    std::map<unsigned int, Glyph> cache;

    Rasterizer(const Rasterizer &);
    Rasterizer &operator=(const Rasterizer &);

public:
    Rasterizer() : dc(CreateCompatibleDC(NULL)), font(NULL), oldFont(NULL),
                   size(0), lineHeight(0) {}

    ~Rasterizer()
    {
        if (oldFont) SelectObject(dc, oldFont);
        if (font) DeleteObject(font);
        if (dc) DeleteDC(dc);
    }

    bool setSize(int pixels, const wchar_t *requestedFace = NULL)
    {
        if (!dc) return false;
        bool bundled = LoadBundledFonts();
        const wchar_t *face = requestedFace && *requestedFace ? requestedFace :
            (pixels < 11 ? L"Fusion Pixel 8px Mono zh-Hans" : L"Fusion Pixel 12px Mono zh-Hans");
        if ((!requestedFace || !*requestedFace) && !bundled)
        {
#ifdef VBA_ZH_SOURCE_BUILD
            return false;
#else
            face = L"SimSun"; // Resource-less developer harnesses only.
#endif
        }
        if (pixels == size && font && faceName == face) return true;
        HFONT next = CreateFontW(-pixels, 0, 0, 0, FW_NORMAL, FALSE, FALSE,
            FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            NONANTIALIASED_QUALITY, DEFAULT_PITCH, face);
        if (!next) return false;
        HGDIOBJ previous = SelectObject(dc, next);
        if (!previous || previous == HGDI_ERROR)
        {
            DeleteObject(next);
            return false;
        }
        if (!oldFont) oldFont = previous;
        if (font) DeleteObject(font);
        font = next;
        size = pixels;
        faceName = face;
        TEXTMETRICW metric;
        if (!GetTextMetricsW(dc, &metric)) return false;
        lineHeight = metric.tmHeight + metric.tmExternalLeading;
        SetTextColor(dc, RGB(255, 255, 255));
        SetBkColor(dc, RGB(0, 0, 0));
        SetBkMode(dc, OPAQUE);
        SetTextAlign(dc, TA_TOP | TA_LEFT | TA_NOUPDATECP);
        cache.clear();
        return true;
    }

    int height() const { return lineHeight; }

    const Glyph *get(unsigned int codepoint)
    {
        std::map<unsigned int, Glyph>::iterator found = cache.find(codepoint);
        if (found != cache.end()) return &found->second;
        WCHAR chars[2];
        int count = 1;
        if (codepoint > 0xffff)
        {
            unsigned int value = codepoint - 0x10000;
            chars[0] = (WCHAR)(0xd800 + (value >> 10));
            chars[1] = (WCHAR)(0xdc00 + (value & 0x3ff));
            count = 2;
        }
        else chars[0] = (WCHAR)codepoint;
        SIZE extent;
        if (!font || !GetTextExtentPoint32W(dc, chars, count, &extent))
            return NULL;
        Glyph glyph;
        glyph.width = extent.cx > 0 ? extent.cx : 1;
        glyph.height = extent.cy > 0 ? extent.cy : lineHeight;
        BITMAPINFO info = {0};
        info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
        info.bmiHeader.biWidth = glyph.width;
        info.bmiHeader.biHeight = -glyph.height;
        info.bmiHeader.biPlanes = 1;
        info.bmiHeader.biBitCount = 32;
        info.bmiHeader.biCompression = BI_RGB;
        void *bits = NULL;
        HBITMAP bitmap = CreateDIBSection(dc, &info, DIB_RGB_COLORS, &bits, NULL, 0);
        if (!bitmap) return NULL;
        HGDIOBJ oldBitmap = SelectObject(dc, bitmap);
        if (!oldBitmap || oldBitmap == HGDI_ERROR)
        {
            DeleteObject(bitmap);
            return NULL;
        }
        memset(bits, 0, glyph.width * glyph.height * 4);
        BOOL drawn = TextOutW(dc, 0, 0, chars, count);
        GdiFlush();
        if (drawn)
        {
            glyph.mask.resize(glyph.width * glyph.height);
            const unsigned char *pixels = (const unsigned char *)bits;
            for (size_t i = 0; i < glyph.mask.size(); ++i)
                glyph.mask[i] = pixels[i * 4];
        }
        SelectObject(dc, oldBitmap);
        DeleteObject(bitmap);
        if (!drawn) return NULL;
        // Scripts with changing text cannot grow the cache without limit.
        if (cache.size() >= 512) cache.clear();
        return &cache.insert(std::make_pair(codepoint, glyph)).first->second;
    }
};

inline bool Measure(Rasterizer &font, const std::wstring &text, int &width, int &height)
{
    const Glyph *space = font.get(' ');
    if (!space) return false;
    const int tabWidth = space->width * 4;
    __int64 pen = 0, widest = 0, lines = 1;
    for (size_t i = 0; i < text.size(); ++i)
    {
        unsigned int c = text[i];
        if (c == 0xfeff || c == '\r') continue;
        if (c == '\n') { if (pen > widest) widest = pen; pen = 0; ++lines; continue; }
        if (c == '\t') { pen += tabWidth - pen % tabWidth; continue; }
        if (c >= 0xd800 && c <= 0xdbff && i + 1 < text.size())
            c = 0x10000 + ((c - 0xd800) << 10) + (text[++i] - 0xdc00);
        const Glyph *glyph = font.get(c);
        if (!glyph) return false;
        pen += glyph->width;
    }
    if (pen > widest) widest = pen;
    width = (int)(widest < INT_MAX ? widest : INT_MAX);
    __int64 totalHeight = lines * font.height();
    height = (int)(totalHeight < INT_MAX ? totalHeight : INT_MAX);
    return true;
}

// The callback receives only visible, fully rasterized foreground/outline pixels.
template<class Plot>
bool Draw(Rasterizer &font, const std::wstring &text, int x, int y,
          int width, int height, Plot plot, int onlyPass = -1, int outlineStyle = 3)
{
    const int origin = x;
    // Wide arithmetic also handles coordinates supplied at Lua's integer limits.
    const Glyph *space = font.get(' ');
    if (!space) return false;
    const int tabWidth = space->width * 4;
    // Finish all outlines before foregrounds, so adjacent glyphs cannot erase
    // each other's edge strokes (particularly common in full-width Chinese).
    for (int pass = 0; pass < 2; ++pass)
    {
    if ((onlyPass >= 0 && pass != onlyPass) || (pass == 0 && outlineStyle == 0)) continue;
    __int64 penX = x, penY = y;
    for (size_t i = 0; i < text.size(); ++i)
    {
        unsigned int c = text[i];
        if (c == 0xfeff || c == '\r') continue;
        if (c == '\n') { penX = origin; penY += font.height(); continue; }
        if (c == '\t') { penX += tabWidth - (penX - origin) % tabWidth; continue; }
        if (c >= 0xd800 && c <= 0xdbff && i + 1 < text.size())
            c = 0x10000 + ((c - 0xd800) << 10) + (text[++i] - 0xdc00);
        const Glyph *glyph = font.get(c);
        if (!glyph) return false;
        for (int gy = -1; gy <= glyph->height; ++gy)
        {
            __int64 py = penY + gy;
            if (py < 0 || py >= height) continue;
            for (int gx = -1; gx <= glyph->width; ++gx)
            {
                __int64 px = penX + gx;
                if (px < 0 || px >= width) continue;
                if (glyph->ink(gx, gy))
                {
                    if (pass == 1) plot((int)px, (int)py, false);
                }
                else if (pass == 0)
                {
                    bool outline = false;
                    for (int dy = -1; dy <= 1 && !outline; ++dy)
                        for (int dx = -1; dx <= 1; ++dx)
                        {
                            if (outlineStyle == 1 && (dx != -1 || dy != -1)) continue;
                            if (outlineStyle == 2 && dx && dy) continue;
                            if (glyph->ink(gx + dx, gy + dy)) { outline = true; break; }
                        }
                    if (outline) plot((int)px, (int)py, true);
                }
            }
        }
        penX += glyph->width;
    }
    }
    return true;
}
}
#endif
