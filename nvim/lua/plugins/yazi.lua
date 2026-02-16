-- yazi.lua — File manager integration (yazi in a floating window)

return {
    "mikavilpas/yazi.nvim",
    version = "*", -- Use the latest stable release
    event = "VeryLazy",
    dependencies = {
        { "nvim-lua/plenary.nvim", lazy = true },
    },
    keys = {
        -- Open yazi in the current file's directory
        { "<leader>y", "<cmd>Yazi<cr>", mode = "n", desc = "Open yazi file manager" },

        -- Open yazi in current working directory
        { "<leader>Y", "<cmd>Yazi cwd<cr>", mode = "n", desc = "Open yazi in cwd" },

        -- Toggle yazi (reopen at last location)
        { "<leader>ty", "<cmd>Yazi toggle<cr>", mode = "n", desc = "Toggle yazi" },

        -- Quick toggle with Ctrl+Up
        { "<c-up>", "<cmd>Yazi toggle<cr>", mode = "n", desc = "Quick toggle yazi" },
    },
    opts = {
        -- Open yazi instead of netrw for directories
        open_for_directories = true,

        -- Floating window configuration
        floating_window_scaling_factor = 0.9,
        yazi_floating_window_border = "rounded",

        -- Highlight buffers in the same directory
        highlight_hovered_buffers_in_same_directory = true,
    },
}
