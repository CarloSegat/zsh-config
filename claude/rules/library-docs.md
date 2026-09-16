# Library docs

For any library, framework, or engine API question (signature, option, behavior in a given version), read current docs before answering; don't rely on memory. Use the `gitmcp` MCP (any public GitHub repo, free, no key):

1. `match_common_libs_owner_repo_mapping` when only a library name is known.
2. `search_generic_code` on the docs repo to find the file.
3. `fetch_generic_url_content` on the file's raw URL.

`search_generic_documentation` only covers repos with an llms.txt. Godot (`godotengine/godot-docs`) has none: go through code search; the class reference is `classes/class_<name>.rst`.
