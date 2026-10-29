#include "../src/common/lua-win32-text.h"
#include <cassert>
#include <cstdio>
#include "../src/common/System.h"
#include "../src/common/Text.h"

int systemColorDepth = 32, systemRedShift = 19, systemGreenShift = 11, systemBlueShift = 3;
u32 RGB_LOW_BITS_MASK = 0x010101;

struct Canvas
{
    int *foreground, *outline;
    void operator()(int x, int y, bool border) const
    {
        assert(x >= 0 && x < 240 && y >= 0 && y < 160);
        if (border) ++*outline; else ++*foreground;
    }
};

int main()
{
    using namespace LuaWin32Text;
    std::wstring text;
    const char chinese[] = "\xe4\xb8\xad\xe6\x96\x87";
    assert(DecodeUTF8(chinese, sizeof(chinese) - 1, text));
    assert(text == L"\x4e2d\x6587");
    assert(!DecodeUTF8("\xc0\xaf", 2, text)); // overlong
    assert(!DecodeUTF8("\xe4\xb8", 2, text)); // truncated
    assert(!DecodeUTF8("\xed\xa0\x80", 3, text)); // surrogate
    assert(!DecodeUTF8("\xd6\xd0\xce\xc4", 4, text)); // GBK is not UTF-8
    assert(DecodeUTF8("", 0, text) && text.empty());
    assert(DecodeUTF8("\xf0\x9f\x98\x80", 4, text) && text.size() == 2);

    Rasterizer raster;
    assert(raster.setSize(12));
    const Glyph *middle = raster.get(0x4e2d);
    assert(middle && middle->width >= 8);
    std::vector<unsigned char> first = middle->mask;
    int ink = 0;
    for (size_t i = 0; i < first.size(); ++i) ink += first[i] != 0;
    assert(ink > 10);
    const Glyph *writing = raster.get(0x6587);
    assert(writing && writing->mask != first); // distinct glyphs, not identical tofu

    int fg = 0, bg = 0;
    Canvas canvas = { &fg, &bg };
    assert(DecodeUTF8(chinese, sizeof(chinese) - 1, text));
    assert(Draw(raster, text, 4, 4, 240, 160, canvas));
    assert(fg > 10 && bg > 10);
    fg = bg = 0;
    assert(Draw(raster, text, 238, 158, 240, 160, canvas));
    assert(Draw(raster, text, -6, -6, 240, 160, canvas));
    fg = bg = 0;
    assert(Draw(raster, text, INT_MAX, INT_MIN, 240, 160, canvas));
    assert(fg == 0 && bg == 0);
    assert(Draw(raster, L"A\t\x4e2d\n\x6587\rB", 0, 0, 240, 160, canvas));
    assert(fg > 0);
    DWORD before = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    for (int round = 0; round < 3; ++round)
    {
        assert(raster.setSize(12 + round));
        for (unsigned int c = 0x4e00; c < 0x5100; ++c) assert(raster.get(c));
    }
    DWORD after = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    assert(after <= before + 1);
    // Exercise the actual system-message renderer, including all pixel formats.
    char localized[64];
    assert(WideCharToMultiByte(CP_ACP, 0, L"\x4e2d\x6587", -1, localized, sizeof(localized), NULL, NULL));
    for (int depth = 16; depth <= 32; depth += 8)
    {
        systemColorDepth = depth;
        systemRedShift = depth == 16 ? 11 : 19;
        systemGreenShift = depth == 16 ? 6 : 11;
        systemBlueShift = depth == 16 ? 0 : 3;
        RGB_LOW_BITS_MASK = depth == 16 ? 0x821 : 0x010101;
        int pitch = 64 * (depth / 8), size = pitch * 32;
        std::vector<u8> buffer(size + 128, 17);
        assert(!drawTextMultibyte(&buffer[64], pitch, 0, 0, 64, 32, "ASCII"));
        assert(drawTextMultibyte(&buffer[64], pitch, -4, -4, 64, 32, localized));
        assert(drawTextMultibyte(&buffer[64], pitch, 62, 30, 64, 32, localized));
        transparentText = true;
        assert(drawTextMultibyte(&buffer[64], pitch, 0, 12, 64, 32, localized));
        transparentText = false;
        int changed = 0;
        for (int i = 0; i < size; ++i) changed += buffer[64 + i] != 17;
        assert(changed > 10);
        for (int i = 0; i < 64; ++i) assert(buffer[i] == 17 && buffer[size + 64 + i] == 17);
    }
    printf("PASS: UTF-8 validation, distinct Chinese glyphs, outline, clipping, multiline, bounded cache, GDI handles\n");
    printf("PASS: actual status renderer, 16/24/32-bit, transparency, clipped buffer guards (ACP=%u)\n", GetACP());
    return 0;
}
