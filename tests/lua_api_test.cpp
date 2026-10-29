#include "../src/common/lua-win32-text.h"
#include <cassert>
#include <cstdio>
extern "C" {
#include "../src/lua/src/lua.h"
#include "../src/lua/src/lauxlib.h"
#include "../src/lua/src/lualib.h"
}
typedef unsigned int uint32;
#define LUA_SCREEN_WIDTH 256
#define LUA_SCREEN_HEIGHT 224
#define LUA_BUILD_PIXEL(a,r,g,b) (((uint32)(a)<<24)|((r)<<16)|((g)<<8)|(b))
static int drawn = 0;
static void gui_prepare() {}
static void gui_drawpixel_internal(int x, int y, uint32 color)
{
    assert(x >= 0 && y >= 0 && x < LUA_SCREEN_WIDTH && y < LUA_SCREEN_HEIGHT);
    if (color >> 24) ++drawn;
}
static uint32 gui_optcolour(lua_State *L, int index, uint32 fallback)
{
    if (!lua_isnumber(L, index)) return fallback;
    uint32 rgba = (uint32)lua_tonumber(L, index);
    return (rgba >> 8) | (rgba << 24);
}

// Generated from lua-engine.cpp, so this exercises the real new Lua entry point.
#include "../build/checks/lua_utf8_entry.inc"

int main()
{
    lua_State *L = luaL_newstate();
    assert(L);
    luaL_openlibs(L);
    lua_newtable(L);
    lua_pushcfunction(L, gui_textutf8);
    lua_setfield(L, -2, "textutf8");
    lua_setglobal(L, "gui");
    const char *script =
        "gui.textutf8(4,4,'\xe4\xb8\xad\xe6\x96\x87')\n"
        "assert(not pcall(gui.textutf8,0,0,string.char(0xd6,0xd0)))\n"
        "assert(not pcall(gui.textutf8,0,0,'test',nil,nil,100))\n"
        "assert(not pcall(gui.textutf8,0,0,{}))\n"
        "gui.textutf8(-10,-10,'\xe4\xb8\xad\xe6\x96\x87',nil,nil,16)\n";
    if (luaL_dostring(L, script))
    {
        fprintf(stderr, "%s\n", lua_tostring(L, -1));
        return 1;
    }
    assert(drawn > 10);
    drawn = 0;
    assert(luaL_dostring(L, "gui.textutf8(0,0,'\xe4\xb8\xad',0,0)") == 0);
    assert(drawn == 0);
    lua_close(L);
    puts("PASS: actual gui.textutf8 entry point with supplied Lua 5.1 DLL, Chinese, invalid UTF-8, bad size/type, clipping, zero alpha");
    return 0;
}
