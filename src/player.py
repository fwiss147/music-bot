def load_opus() -> None:
    try:
        if discord.opus.is_loaded():
            return
    except Exception:
        pass

    import glob

    # مسارات خاصة بـ Railway و Nixpacks و Linux
    custom_paths = (
        glob.glob("/nix/store/*opus*/lib/libopus.so*")
        + glob.glob("/root/.nix-profile/lib/libopus.so*")
        + glob.glob("/usr/lib/**/libopus.so*", recursive=True)
        + ["libopus.so.0", "libopus.so", "libopus"]
    )

    for path in custom_paths:
        if path:
            try:
                discord.opus.load_opus(path)
                if discord.opus.is_loaded():
                    log.info("Loaded libopus successfully from %s", path)
                    return
            except Exception:
                pass

    found = ctypes.util.find_library("opus")
    if found:
        try:
            discord.opus.load_opus(found)
            log.info("Loaded libopus from %s", found)
            return
        except Exception:
            log.debug("Could not load libopus from %s", found, exc_info=True)

    try:
        import av

        lib_dir = Path(av.__file__).parent / ".dylibs"
        candidates = list(lib_dir.glob("libopus*.dylib")) + list(lib_dir.glob("libopus*.so*"))
    except Exception:
        candidates = []

    for candidate in candidates:
        try:
            discord.opus.load_opus(str(candidate))
            log.info("Loaded libopus from %s", candidate)
            return
        except Exception:
            log.debug("Could not load libopus from %s", candidate, exc_info=True)

    try:
        if not discord.opus.is_loaded():
            log.warning("libopus is not available; voice playback will fail")
    except Exception:
        pass
