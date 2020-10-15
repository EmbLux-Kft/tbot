import abc
import tbot
import time
from tbot.machine import board

__all__ = ("SispmControl",)


class SispmControl(board.PowerControl):
    """
    control Power On/off with sispmctl

    http://sispmctl.sourceforge.net/

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbot_contrib.powercontrol import sispmctl

        class MyControl(sispmctl.SispmControl, board.Board):
            sispmctl_device = "01:01:5c:29:39"
            sispmctl_port = "2"
    """

    @property
    @abc.abstractmethod
    def sispmctl_device(self) -> str:
        """
        Device used. Get device id with
        sispcmtl -s

        This property is **required**.
        """
        raise Exception("abstract method")

    @property
    @abc.abstractmethod
    def sispmctl_port(self) -> str:
        """
        port used.

        This property is **required**.
        """
        raise Exception("abstract method")

    def poweron(self) -> None:
        self.host.exec0(
            "sispmctl", "-D", self.sispmctl_device, "-o", self.sispmctl_port
        )

    def poweroff(self) -> None:
        if "nopoweroff" in tbot.flags:
            tbot.log.message("Waiting a bit to let power settle down ...")
        else:
            self.host.exec0(
                "sispmctl", "-D", self.sispmctl_device, "-f", self.sispmctl_port
            )

            tbot.log.message("Waiting a bit to let power settle down ...")
            time.sleep(2)
