# farmina
a fairly simple farm for A/D CTFs

To run it, you need to export the environment variables specified in `.env.example` and then just run `./farmina.py` (I recommend making a simple script to export + run)

### architecture
it's made up of 3 parts:
- `/config` FastAPI endpoint to get the config (:mind_blown:)
- `/flags` FastAPI endpoint to ingest the flags from the clients
- `submission_worker`, the main loop which submits the stolen flags to the game system in order to score points for the team

to store flags it uses a simple [sqlite](https://sqlite.org/) database (`./flags.db` by default) with the flag as primary key, where it also keeps track of the flag's status from the game system along with its message (so it will also have the points gained, depending on the game system type)

it can optionally print the sum of the points gained each time it submits a batch of flags, but it needs a regex like `Accepted: ([0-9.]+) flag points`[^1], with the first capture group being the one used to find the points in the message (if the game system provides them)

### dependencies 
- [`python-requests`](https://requests.readthedocs.io/)
- [`python-fastapi`](https://fastapi.tiangolo.com/)
- [`uvicorn`](https://uvicorn.dev/) (to run fastapi)
- [`python-peewee`](http://docs.peewee-orm.com/) (for sqlite)

# clientino
a very simple client for farmina

it can be used like `./clientino.py -H host -P port exploit.py`, and it will run `exploit.py` (which can be any file marked as executable[^2]) every `-i`/`--interval` seconds[^3] using, each time, `-j`/`--jobs` concurrent subprocesses[^4], each ran against 1 team and will `POST` the flags found in the script's output (using `FLAG_REGEX`) to `http://host:port/flags`

as with the other farms, the exploit script has to take 1 argument, which will be the currently attacked team's vm's IP address
### dependencies 
- [`python-requests`](https://requests.readthedocs.io/)

# *types types types types*
even tho it's a very simple farm, it's still strictly typed, so if you want to type check it, you need
- a type checker for python (e.g. [`mypy`](https://mypy-lang.org/))
- [`python-types-requests`](https://pypi.org/project/types-requests/)
- [`python-types-peewee`](https://pypi.org/project/types-peewee/) note: `execute()` as is not typed yet, so you will need to tell the checker to ignore its untyped calls

_P.S. coming from haskell, type checking in python sucks, but it could also be that I don't have mypy set up correctly so idk_

[^1]: this is from [ctfbox](https://github.com/domysh/ctfbox)
[^2]: so also a `.sh`, `.lua`, a normal ELF, as long as it has a [shebang](https://en.wikipedia.org/wiki/Shebang_(Unix)) if text or is in a format that [linux recognizes it as executable](https://docs.kernel.org/admin-guide/binfmt-misc.html)
[^3]: `30.0` by default
[^4]: `1` by default
