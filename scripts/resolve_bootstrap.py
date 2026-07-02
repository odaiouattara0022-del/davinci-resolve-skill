#!/usr/bin/env python3
"""Connect to a running DaVinci Resolve instance from any external Python script.

Usage as a module:
    from resolve_bootstrap import get_resolve
    resolve = get_resolve()

Usage as a health check:
    python resolve_bootstrap.py
"""
import os
import sys
import platform


def _default_paths():
    """Per-OS locations of the scripting module and fusionscript library."""
    system = platform.system()
    if system == "Windows":
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return {
            "api": os.path.join(program_data, "Blackmagic Design", "DaVinci Resolve",
                                "Support", "Developer", "Scripting"),
            "lib": r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll",
        }
    if system == "Darwin":
        return {
            "api": "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting",
            "lib": "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so",
        }
    return {  # Linux
        "api": "/opt/resolve/Developer/Scripting",
        "lib": "/opt/resolve/libs/Fusion/fusionscript.so",
    }


def get_resolve():
    """Return the Resolve scripting object, or raise RuntimeError with a fix hint."""
    paths = _default_paths()
    os.environ.setdefault("RESOLVE_SCRIPT_API", paths["api"])
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", paths["lib"])
    modules_path = os.path.join(os.environ["RESOLVE_SCRIPT_API"], "Modules")
    if modules_path not in sys.path:
        sys.path.append(modules_path)

    try:
        import DaVinciResolveScript as dvr
    except ImportError as exc:
        raise RuntimeError(
            "Could not import DaVinciResolveScript.\n"
            f"  Looked in: {modules_path}\n"
            "  Is DaVinci Resolve installed? If it lives in a non-default location,\n"
            "  set RESOLVE_SCRIPT_API and RESOLVE_SCRIPT_LIB environment variables."
        ) from exc

    resolve = dvr.scriptapp("Resolve")
    if resolve is None:
        raise RuntimeError(
            "DaVinciResolveScript loaded but no Resolve instance answered.\n"
            "  1. Is DaVinci Resolve running?\n"
            "  2. Preferences > System > General > 'External scripting using' must be 'Local'.\n"
            "  3. Restart Resolve after changing that preference."
        )
    return resolve


def main():
    try:
        resolve = get_resolve()
    except RuntimeError as exc:
        print(f"NOT CONNECTED\n{exc}")
        return 1

    print(f"CONNECTED: {resolve.GetProductName()} {resolve.GetVersionString()}")
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        print("No project open.")
        return 0
    print(f"Project:  {project.GetName()}")
    timeline = project.GetCurrentTimeline()
    if timeline:
        print(f"Timeline: {timeline.GetName()} "
              f"({timeline.GetTrackCount('video')} video / {timeline.GetTrackCount('audio')} audio tracks)")
    else:
        print("No timeline open.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
