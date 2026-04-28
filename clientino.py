#!/bin/python
import argparse
import re
import pexpect
import requests
import time
from typing import TypedDict, cast, Iterable
from concurrent.futures import ThreadPoolExecutor

type Flag = str
type Team = str


class FarmConfig(TypedDict):
    flag_regex: str
    teams: list[Team]


def get_config(url: str) -> FarmConfig:
    r: requests.Response = requests.get(f"{url}/config", timeout=5)
    r.raise_for_status()
    return cast(FarmConfig, r.json())


def submit_flags(url: str, flags: list[Flag]) -> None:
    try:
        r: requests.Response = requests.post(f"{url}/flags", json=flags, timeout=5)
        r.raise_for_status()
    except Exception as e:
        print(f"error submitting flags: {e}")


def run_on_team(script: str, ip: Team, regex: str, url: str) -> list[Flag]:
    try:
        found: list[Flag] = []
        child: pexpect.spawn[str] = pexpect.spawn(
            script, [ip],
            encoding='utf-8',
            codec_errors='ignore',
            timeout=None,
            maxread=1
        )
        try:
            line: str
            for line in child:
                if line_flags := re.findall(regex, line):
                    print(f"{ip}: {line_flags}")
                    submit_flags(url, line_flags)
                    found += line_flags
        except pexpect.EOF:
            pass
        finally:
            child.close()
        return found
    except Exception as e:
        print(f"error on {ip}: {e}")
        return []


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("script")
    parser.add_argument("-H", "--host", required=True, help="farmina server host")
    parser.add_argument("-P", "--port", required=True, type=int, help="farmina server port")
    parser.add_argument("-i", "--interval", type=float, default=30.0, help="seconds between attacks")
    parser.add_argument("-j", "--jobs", type=int, default=1, help="number of parallel jobs")
    args: argparse.Namespace = parser.parse_args()

    url: str = f"http://{args.host}:{args.port}"

    while True:
        try:
            config: FarmConfig = get_config(url)

            all_flags: list[Flag] = []
            with ThreadPoolExecutor(max_workers=args.jobs) as executor:
                results: Iterable[list[Flag]] = executor.map(
                    lambda ip: run_on_team(str(args.script), ip, config['flag_regex'], url),
                    config['teams']
                )
                for f_list in results:
                    all_flags += f_list

            flags: list[Flag] = list(set(all_flags))  # remove duplicates
            if flags:
                print(f"attack round finished: submitted {len(flags)} unique flags")
        except Exception as e:
            print(f"error: {e}")

        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("ctrl-c, exiting...")
