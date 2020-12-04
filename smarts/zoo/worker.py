import logging
import argparse
import tempfile
import sys
import pathlib
import subprocess

from multiprocessing.connection import Listener

from smarts.core.utils.networking import find_free_port

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(f"Zoo Worker")


def spawn_networked_agent(port, auth_key):
    cmd = [
        sys.executable,  # path to the current python binary
        str((pathlib.Path(__file__).parent / "run_agent.py").absolute().resolve()),
        "--port",
        str(port),
        "--auth_key",
        auth_key,
    ]

    agent_proc = subprocess.Popen(cmd)
    return agent_proc


def spawn_local_agent(socket_file, auth_key):
    cmd = [
        sys.executable,  # path to the current python binary
        str((pathlib.Path(__file__).parent / "run_agent.py").absolute().resolve()),
        "--socket_file",
        socket_file,
        "--auth_key",
        auth_key,
    ]

    agent_proc = subprocess.Popen(cmd)
    return agent_proc


def handle_request(request, auth_key):
    if request == "allocate_networked_agent":
        port = find_free_port()
        proc = spawn_networked_agent(port, auth_key)
        return proc, {"port": port, "result": "success"}

    elif request == "allocate_local_agent":
        sock_file = tempfile.mktemp()
        proc = spawn_local_agent(sock_file, auth_key)
        return proc, {"socket_file": sock_file, "result": "success"}

    else:
        return None, {"result": "error", "msg": "bad request"}


def listen(port, auth_key):
    log.debug(f"Starting Zoo Worker on port {port}")
    agent_procs = []
    try:
        with Listener(("0.0.0.0", port), "AF_INET", authkey=auth_key) as listener:
            while True:
                with listener.accept() as conn:
                    log.debug(f"Accepted connection {conn}")
                    try:
                        request = conn.recv()
                        log.debug(f"Received request {request}")

                        proc, resp = handle_request(request, auth_key)
                        if proc:
                            log.debug("Created agent proc")
                            agent_procs.append(proc)

                        log.debug(f"Responding with {resp}")
                        conn.send(resp)
                    except Exception as e:
                        log.error(f"Failure while handling connection {repr(e)}")
    finally:
        log.debug("Cleaning up zoo worker")
        # cleanup
        for proc in agent_procs:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        "Listens for requests to allocate agents and executes them on-demand"
    )
    parser.add_argument(
        "--port", type=int, default=7432, help="Port to listen on",
    )
    parser.add_argument(
        "--auth_key",
        type=str,
        help="Authentication key for connection to run agent",
    )
    args = parser.parse_args()
    args.auth_key = str.encode(args.auth_key)
    listen(args.port, args.auth_key)
