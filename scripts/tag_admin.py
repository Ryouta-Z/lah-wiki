"""Compatibility-free command entry point for the unified local tag manager."""

try:
    from scripts.assistant_tag_admin import main
except ModuleNotFoundError:  # Allow `python scripts/tag_admin.py` from the project root.
    from assistant_tag_admin import main  # type: ignore[no-redef]


if __name__ == "__main__":
    main()
