source /usr/share/cachyos-fish-config/cachyos-config.fish

# overwrite greeting
# potentially disabling fastfetch
#function fish_greeting
#    # smth smth
#end

fish_add_path -g $HOME/.local/bin

# bun
set --export BUN_INSTALL "$HOME/.bun"
fish_add_path -g $BUN_INSTALL/bin

if status is-interactive
    # z <part of a path>: jump to a folder you've been to before (zi to pick from a list)
    zoxide init fish | source
    # Ctrl-R: fuzzy-search history; Ctrl-T: insert a file path; Alt-C: cd into a folder
    fzf --fish | source
    # fzf colours from the wallpaper (Noctalia "fzf" template). Read the colour flags
    # rather than sourcing the file: it appends to a universal variable, which would
    # pile up a copy per shell.
    set -l fzf_theme $HOME/.config/fzf/themes/noctalia.fish
    if test -r $fzf_theme
        set -gx FZF_DEFAULT_OPTS (string match -rg -- '(--color=\S+)' < $fzf_theme)
    end
end
