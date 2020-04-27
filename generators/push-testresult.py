#!/usr/bin/env python3
# tbot, Embedded Automation Tool
# Copyright (C) 2020 Heiko Schocher
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
get all stuff from log and push to U-Boot testresult server.

set following Environment variables:
- SERVER_URL
- SERVER_PORT
- SERVER_USER
- SERVER_PASSWORD
- TBOT_STDIO_LOGFILE
- TBOT_LOGFILE
"""
import logparser
import requests
import os
import sys

# pip3 install requests-toolbelt --user
from requests_toolbelt import MultipartEncoder


class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r


def get_values() -> None:
    """
    """

    try:
        URL = os.environ["SERVER_URL"]
    except KeyError:
        raise RuntimeError("set environment variable SERVER_URL")

    try:
        PORT = os.environ["SERVER_PORT"]
    except KeyError:
        raise RuntimeError("set environment variable SERVER_PORT")

    try:
        user = os.environ["SERVER_USER"]
    except KeyError:
        raise RuntimeError("set environment variable SERVER_USER")

    try:
        password = os.environ["SERVER_PASSWORD"]
    except KeyError:
        raise RuntimeError("set environment variable SERVER_PASSWORD")

    events = logparser.from_argv()

    success = "False"
    soc = "unknown"
    splsize = "0"
    for ev in events:
        if ev.type[0] == "doc":
            if ev.type[1] == "tag":
                if ev.data["tagid"] == "UBOOT_BUILD_TITLE":
                    title = ev.data["tagval"]
                if ev.data["tagid"] == "UBOOT_BUILD_TIME":
                    build_date = ev.data["tagval"]
                if ev.data["tagid"] == "UBOOT_BUILD_ARCH":
                    arch = ev.data["tagval"]
                if ev.data["tagid"] == "UBOOT_BUILD_SOC":
                    soc = ev.data["tagval"]
                if ev.data["tagid"] == "UBOOT_BUILD_CPU":
                    cpu = ev.data["tagval"]
                if ev.data["tagid"] == "BUILD_TOOLCHAIN":
                    toolchain = ev.data["tagval"]
                if ev.data["tagid"] == "UBOOT_BOARD_NAME":
                    boardname = ev.data["tagval"]
                if ev.data["tagid"] == "GIT_CURRENT_COMMIT_ORIGIN":
                    basecommit = ev.data["tagval"]
                if ev.data["tagid"] == "UBOOT_BUILD_DEFCONFIG":
                    defconfig = ev.data["tagval"]
                if ev.data["tagid"] == "UBOOT_SPL_SIZE":
                    splsize = ev.data["tagval"]
                if ev.data["tagid"] == "UBOOT_UBOOT_SIZE":
                    ubsize = ev.data["tagval"]
                if ev.data["tagid"] == "UBOOT_NOTES":
                    content = ev.data["tagval"]
        if ev.type[0] == "tbot":
            if ev.type[1] == "end":
                if ev.data["success"] is True:
                    success = "True"

    try:
        fn = os.environ["TBOT_LOGFILE"]
    except KeyError:
        raise RuntimeError("set environment variable TBOT_LOGFILE")
    try:
        fn2 = os.environ["TBOT_STDIO_LOGFILE"]
    except KeyError:
        raise RuntimeError("set environment variable TBOT_STDIO_LOGFILE")

    m = MultipartEncoder(
        fields={
            "title": title,
            "build_date": build_date,
            "arch": arch,
            "cpu": cpu,
            "soc": soc,
            "toolchain": toolchain,
            "boardname": boardname,
            "basecommit": basecommit,
            "defconfig": defconfig,
            "splsize": splsize,
            "ubsize": ubsize,
            "success": success,
            "content": content,
            "tbotlog": ("filename", open(fn2, "rb"), "text/plain"),
            "tbotjson": ("filename", open(fn, "rb"), "text/plain"),
        }
    )

    print("NEWRESULT ", m)
    if PORT != "":
        location = f"{PORT}/api"
        sep = ":"
    else:
        location = f"api"
        sep = "/"

    print("GET token ------------------- ")
    s = requests.Session()
    s.auth = (user, password)
    loc = f"{location}/tokens"
    url = f"{URL}{sep}{loc}"
    r = s.post(url=url)

    if r.status_code != 200:
        raise RuntimeError(f"got status code {r.status_code}")

    print("R ", r)
    print("R status code ", r.status_code)
    data = r.json()
    print("DATA ", data)

    tok = data["token"]

    loc = f"{location}/result/{defconfig}"
    print(f"GET last {defconfig} result ------------------- {loc}")
    r = s.get(url=f"{URL}{sep}{loc}", auth=BearerAuth(tok))

    print("R ", r)
    print("R status code ", r.status_code)
    if r.status_code == 200:
        data = r.json()
        print("DATA ", data)

        if data["basecommit"] == basecommit and data["toolchain"] == toolchain:
            suc = "False"
            if data["success"] == True:
                suc = "True"
            if suc == success:
                print("no new testresult")
                sys.exit(0)

    loc = f"{location}/newresult"
    print("DATA ", m)
    r = s.post(
        url=f"{URL}{sep}{loc}",
        auth=BearerAuth(tok),
        data=m,
        headers={"Content-Type": m.content_type},
    )

    print("R ", r)
    print("R status code ", r.status_code)
    if r.status_code != 201:
        raise RuntimeError(f"got status code {r.status_code}")

    data = r.json()
    print("DATA ", data)


def main() -> None:
    get_values()


if __name__ == "__main__":
    main()
