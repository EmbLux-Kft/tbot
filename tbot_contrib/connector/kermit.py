import abc
import contextlib
from tbot.machine import channel, connector, linux

__all__ = ("KermitConnector",)


class KermitConnector(connector.ConsoleConnector):
    """
    Connect to a serial console using kermit

    You can configure the device name using the ``kermit_cfg_file`` property.

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbot_contrib.connector import kermit

        class MyBoard(kermit.KermitConnector, board.Board):
            kermit_cfg_file = "path to config file"

        BOARD = MyBoard
    """

    @property
    @abc.abstractmethod
    def kermit_cfg_file(self) -> str:
        """
        kermit config file

        This property is **required**.
        """
        raise Exception("abstract method")

    @contextlib.contextmanager
    def kermitconnect(self, mach: linux.LinuxShell) -> channel.Channel:
        KERMIT_PROMPT = b"C-Kermit>"
        ch = mach.open_channel("kermit", self.kermit_cfg_file)
        try:
            try:
                ret = ch.read(150, timeout=2)
                buf = ret.decode(errors="replace")
                if "Locked" in buf:
                    raise RuntimeError(f"serial line is locked {buf}")
            except TimeoutError:
                pass

            yield ch
        finally:
            ch.sendcontrol("\\")
            ch.send("C")
            ch.read_until_prompt(KERMIT_PROMPT)
            ch.sendline("exit")

    def connect(self, mach: linux.LinuxShell) -> channel.Channel:
        return self.kermitconnect(mach)
