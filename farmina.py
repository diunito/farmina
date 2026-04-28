#!/bin/python
import threading
import requests
import os
import time
import re
from typing import Literal, TypedDict, AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from peewee import SqliteDatabase, Model, CharField

type Flag = str
type Team = str
type SystemFlagStatus = Literal["ACCEPTED", "DENIED", "RESUBMIT", "ERROR"]


class FlagResponse(TypedDict):
    msg: str
    flag: Flag
    status: SystemFlagStatus


class FarmConfig(TypedDict):
    flag_regex: str
    teams: list[Team]


UVICORN_LOG_LEVEL: str = os.getenv('UVICORN_LOG_LEVEL', 'warning')

FARM_HOST: str = os.getenv('FARM_HOST', '0.0.0.0')
FARM_PORT: int = int(os.environ['FARM_PORT'])
SUBMIT_URL: str = os.environ['SUBMIT_URL']  # http://10.10.0.1:8080/flags
TEAM_TOKEN: str = os.environ['TEAM_TOKEN']
RATE_LIMIT_WAIT: float = float(os.environ['RATE_LIMIT_WAIT'])
FLAG_REGEX: str = os.environ['FLAG_REGEX']
NUM_TEAMS: int = int(os.environ['NUM_TEAMS'])
TEAM_IP_FORMAT: str = os.environ['TEAM_IP_FORMAT']
DB_FILE: str = os.getenv('FLAGS_DB', 'flags.db')
FLAGS_CHUNK_SIZE: int = int(os.getenv('FLAGS_CHUNK_SIZE', 2000))
POINTS_REGEX: str = os.getenv('POINTS_REGEX', '')

TEAMS: list[Team] = [TEAM_IP_FORMAT.format(i) for i in range(0, NUM_TEAMS)]

db: SqliteDatabase = SqliteDatabase(DB_FILE)


class FlagRecord(Model):
    flag = CharField(primary_key=True)
    status = CharField(default='QUEUED')
    msg = CharField(default='')

    class Meta:
        database = db


def init_db() -> None:
    db.connect()
    db.create_tables([FlagRecord])
    db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    print("db initialized")
    threading.Thread(target=submission_worker, daemon=True).start()
    print("submission worker started")
    yield
    print("exiting")


app = FastAPI(lifespan=lifespan)


@app.get("/config")
def get_config() -> FarmConfig:
    return {"flag_regex": FLAG_REGEX, "teams": TEAMS}


@app.post("/flags")
def ingest_flags(new: list[Flag], req: Request) -> dict[str, str | int]:
    if not new:
        raise HTTPException(status_code=400, detail="Empty")
    client_ip: str = req.client.host if req.client else "unknown"
    try:
        data: list[dict[str, Flag]] = [{'flag': f} for f in new]
        with db.atomic():
            inserted: list[Flag] = FlagRecord.insert_many(data).on_conflict_ignore().returning(FlagRecord.flag)
        print(f"inserted {len(inserted)} new flags from client {client_ip}")
    except Exception as e:
        print(f"error inserting flags from client {client_ip}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "accepted", "count": len(new)}


def submission_worker() -> None:
    """Background thread to submit flags using Peewee."""
    while True:
        try:
            if db.is_closed():
                db.connect()

            query: list[FlagRecord] = list(FlagRecord.select().where(FlagRecord.status == 'QUEUED').limit(FLAGS_CHUNK_SIZE))
            batch: list[Flag] = [str(r.flag) for r in query]

            if not query:
                time.sleep(1)  # wait for more flags if there are none
                continue

            resp: requests.Response = requests.put(
                SUBMIT_URL, headers={'X-Team-Token': TEAM_TOKEN},
                json=batch, timeout=20
            )

            if resp.status_code == 200:
                responses: list[FlagResponse] = resp.json()
                points: float = 0.0
                with db.atomic():
                    for r in responses:
                        print(r['msg'])
                        if r['status'] == "ACCEPTED" and POINTS_REGEX:
                            match: re.Match[str] | None = re.search(POINTS_REGEX, r['msg'])
                            if match:
                                try:
                                    points += float(match.group(1))
                                except Exception:
                                    pass
                        if r['status'] in ("ACCEPTED", "DENIED"):
                            FlagRecord.update(status=r['status'], msg=r['msg']).where(FlagRecord.flag == r['flag']).execute()
                # "from N teams" can be added since the CCIT format now has round, service and team
                # encoded in the flag itself
                print(f"submitted {len(batch)} flags, got {points} points")
        except Exception as e:
            print(f"error: {e}")

        time.sleep(RATE_LIMIT_WAIT)


if __name__ == "__main__":
    try:
        uvicorn.run(app, host=FARM_HOST, port=FARM_PORT, log_level=UVICORN_LOG_LEVEL)
    except KeyboardInterrupt:
        print("got ctrl-c, exiting")
