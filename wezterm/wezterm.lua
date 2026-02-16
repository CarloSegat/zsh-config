local wezterm = require 'wezterm'
local config = wezterm.config_builder()

-- 1. VISUALS (The "DevOps Toolbox" look)
config.color_scheme = 'tokyonight_night'
config.font = wezterm.font("JetBrains Mono")
config.font_size = 14.0
config.window_decorations = "RESIZE" -- Removes the bulky title bar
config.hide_tab_bar_if_only_one_tab = true

-- 2. TMUX COMPATIBILITY
-- This ensures WezTerm doesn't intercept keys tmux needs
config.disable_default_key_bindings = false

-- 3. IMAGE SUPPORT (For Yazi)
-- WezTerm supports this natively, but we ensure it's allowed
config.allow_square_glyphs_to_overflow_width = "Always"

config.window_decorations = 'RESIZE'

config.keys = {
    {
	key = 'w',
	mods = 'CMD',
	action = wezterm.action.CloseCurrentPane { confirm = false },
    },
    {
	key = 'q',
	mods = 'CTRL',
	action = wezterm.action.ToggleFullScreen,
    },
}

return config
