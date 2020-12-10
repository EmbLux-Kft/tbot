import abc
import contextlib
import typing
import tbot
from tbot.machine import machine
from tbot.machine import linux
from typing import List

H = typing.TypeVar("H", bound=linux.LinuxShell)


class UUULoad(machine.Initializer):
    """
    Machine-initializer for loading SPL/U-Boot image into
    RAM with uuu tool from NXP and using
    Serial Download over USB

    source:
    https://github.com/NXPmicro/mfgtools.git

    installation:
    https://github.com/NXPmicro/mfgtools#how-to-build

    We may can check if tool is installed and if not
    install it automagically...

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbot_contrib.powercontrol import sispmctl
        from tbot_contrib.powercontrol import uuu

        class MyControl(sispmctl.SispmControl, board.Board):
            sispmctl_device = "01:01:5c:29:39"
            sispmctl_port = "2"

        class MyControlLoadUB(MyControl, uuu.UUULoad):
            def get_uuu_tool(self):
                p = self.host.toolsdir()
                return p / "mfgtools"

            def uuu_loader_steps(self):
                p = self.host.yocto_result_dir()
                return [linux.Raw(f"SDP: boot -f /srv/tftpboot/SPL"),
                    linux.Raw(f"SDPV: delay 100"),
                    linux.Raw(f"SDPV: write -f /srv/tftpboot/u-boot-dtb.img -addr 0x877fffc0 -skipfhdr"),
                    linux.Raw(f"SDPV: jump -addr 0x877fffc0"),
                    ]

    This class sets also a tbot flag "uuuloader"

    if passed to tbot, this class is active, if not passed
    this class does nothing.
    """

    @abc.abstractmethod
    def get_uuu_tool(self) -> linux.Path[H]:
        """
            def get_uuu_tool(self) -> linux.Path:
                return lh.workdir / "tools" / "mfgtools"

        :rtype: linux.Path
        :returns: Path to the uuu directory on your LabHost
        """
        pass

    @abc.abstractmethod
    def uuu_loader_steps(self) -> List[str]:
        """
        return list of steps to do for uuu tool

            def uuu_loader_steps(self):
                p = self.host.yocto_result_dir()
                return [linux.Raw(f"SDP: boot -f /srv/tftpboot/SPL"),
                    linux.Raw(f"SDPV: delay 100"),
                    linux.Raw(f"SDPV: write -f /srv/tftpboot/u-boot-dtb.img -addr 0x877fffc0 -skipfhdr"),
                    linux.Raw(f"SDPV: jump -addr 0x877fffc0"),
                    ]

        This property is **required**.
        """
        raise Exception("abstract method")

    @contextlib.contextmanager
    def _init_machine(self) -> typing.Iterator:
        if "uuuloader" not in tbot.flags:
            yield None

        uuu = self.get_uuu_tool()  # type: ignore
        steps = self.uuu_loader_steps()  # type: List[str]
        for st in steps:
            self.host.exec0("sudo", uuu / "uuu/uuu", st)  # type: ignore

        yield None


FLAGS = {
    "uuuloader": "load images with uuu tool",
}
