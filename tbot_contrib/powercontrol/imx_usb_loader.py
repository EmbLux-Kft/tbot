import abc
import contextlib
import typing
from tbot.machine import machine
from tbot.machine import linux
from typing import List
import time

H = typing.TypeVar("H", bound=linux.LinuxShell)


class UsbSdpLoad(machine.Initializer):
    """
    Machine-initializer for loading SPL/U-Boot image into
    RAM with imx_usb_loader tool from NXP and using
    Serial Download over USB

    source:
    https://github.com/boundarydevices/imx_usb_loader

    installation of tool:
    https://github.com/boundarydevices/imx_usb_loader/blob/master/README.md#installation

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbot_contrib.powercontrol import sispmctl
        from tbot_contrib.powercontrol import imx_usb_loader

        class MyControl(sispmctl.SispmControl, board.Board):
            sispmctl_device = "01:01:5c:29:39"
            sispmctl_port = "2"

        class MyControlLoadUB(MyControl, imx_usb_loader.UsbSdpLoad):
            def get_imx_usb_loader(self):
                p = self.host.toolsdir()
                return p / "imx_usb_loader"


            def usb_loader_bins(self):
                p = self.host.yocto_result_dir()
                return [ p / "SPL.signed", p / "u-boot-ivt.img.signed"]

    """

    @abc.abstractmethod
    def get_imx_usb_loader(self) -> linux.Path[H]:
        """
            def get_imx_usb_loader(self) -> linux.Path:
                return lh.workdir / "tools" / "imx_usb_loader"

        :rtype: linux.Path
        :returns: Path to the imx_usb_loader directory on your LabHost
        """
        pass

    @abc.abstractmethod
    def usb_loader_bins(self) -> List[str]:
        """
        return list of linux.Path to usb loader binaries

            def usb_loader_bins(self):
                p = self.host.yocto_result_dir()
                return [ p / "SPL.signed", p / "u-boot-ivt.img.signed"]

        This property is **required**.
        """
        raise Exception("abstract method")

    usb_loader_retry: int = 4
    """retry to load binary retry times"""

    @contextlib.contextmanager
    def _init_machine(self) -> typing.Iterator:
        imx = self.get_imx_usb_loader()
        bins = self.usb_loader_bins()
        for bina in bins:
            loop = True
            i = 0
            time.sleep(3)
            while loop:
                if i:
                    time.sleep(2)
                ret, out = self.host.exec("sudo", imx / "imx_usb", bina)
                if "no matching USB device found" in out and ret == 1:
                    i += 1
                elif ret:
                    raise RuntimeError(f"imx_usb loader failed with {ret}")
                if "failed" in out:
                    raise RuntimeError(f"imx_usb loader failed with {out}")
                if "jumping to" in out:
                    loop = False
                elif i >= self.usb_loader_retry:
                    raise RuntimeError(
                        f"could not load {bina} with imx_usb_loader. retry {self.usb_loader_retry}"
                    )

        yield None
