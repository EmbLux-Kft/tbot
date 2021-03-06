import tbot
from tbot.tc import shell
from tbot.machine import linux


@tbot.testcase
@tbot.with_lab
def swupdate_update_web(
    lh: linux.Lab, swu_file: linux.Path, target_ip: str, timeout: int = 300
) -> None:
    """
    Upload an ``.swu`` file to a running swupdate server.

    :param linux.Lab lh: Optionally the lab-host from where to initiate the update.
    :param linux.Path swu_file: Path to the ``.swu`` file (on the lab-host or locally).
    :param str target_ip: IP-Address of the target host.
    :param int timeout: Timeout.
    """
    with tbot.acquire_local() as lo:  # Needed for the script
        script_path = lh.workdir / "tbot_swupdate_web.py"
        swu_path = lh.workdir / "image.swu"
        script_source = linux.Path(lo, __file__).parent / "swupdate_script.py"
        shell.copy(script_source, script_path)
        shell.copy(swu_file, swu_path)
        lh.exec0("python3", script_path, swu_path, target_ip, str(timeout))
