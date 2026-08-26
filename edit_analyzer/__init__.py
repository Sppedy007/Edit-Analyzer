"""Edit Analyzer package."""

import shutil
import sys
import subprocess


def get_ffmpeg_cmd() -> str:
    """
    Get the path or command string to execute ffmpeg.
    Checks system PATH first, then falls back to imageio-ffmpeg.
    Raises RuntimeError if ffmpeg cannot be found.
    """
    system_path = shutil.which("ffmpeg")
    if system_path is not None:
        return system_path
    
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    raise RuntimeError(
        "ffmpeg binary not found. Please install ffmpeg or imageio-ffmpeg."
    )


def check_ffmpeg_installed() -> bool:
    """
    Check if ffmpeg is available on the system PATH or via imageio-ffmpeg.
    If missing, print clear installation instructions and return False.
    """
    try:
        cmd = get_ffmpeg_cmd()
        res = subprocess.run(
            [cmd, "-version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass

    sys.stderr.write(
        "\n"
        "======================================================================\n"
        " ERROR: ffmpeg is not installed or not found on system PATH!\n"
        " Edit Analyzer requires ffmpeg for video frame and audio extraction.\n"
        " \n"
        " Installation Instructions (Windows):\n"
        "   1. Via winget: `winget install ffmpeg`\n"
        "   2. Via Chocolatey: `choco install ffmpeg`\n"
        "   3. Manual: Download binaries from https://ffmpeg.org and add the `bin` \n"
        "      folder to your Windows PATH environment variable.\n"
        "======================================================================\n\n"
    )
    return False

