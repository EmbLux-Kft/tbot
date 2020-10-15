.. py:module:: tbot_contrib.connector

``tbot_contrib.connector``
==========================
A module containing various additional connectors for convenience.  These
are:

- :py:class:`~tbot_contrib.connector.conserver.ConserverConnector` - Console using `conserver`_.
- :py:class:`~tbot_contrib.connector.pyserial.PyserialConnector` - Console on localhost using `pyserial`_.
- :py:class:`~tbot_contrib.connector.kermit.KermitConnector` - Console on localhost using `kermit`_.

.. _conserver: https://www.conserver.com/
.. _pyserial: https://github.com/pyserial/pyserial
.. _kermit: http://www.kermitproject.org/

.. autoclass:: tbot_contrib.connector.conserver.ConserverConnector
   :members: conserver_device, conserver_master, conserver_command, conserver_forcerw

.. autoclass:: tbot_contrib.connector.pyserial.PyserialConnector
   :members: serial_port, baudrate

.. autoclass:: tbot_contrib.connector.kermit.KermitConnector
   :members: kermit_cfg_file
