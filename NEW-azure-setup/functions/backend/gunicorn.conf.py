"""
Gunicorn production configuration.

Usage:
  gunicorn -c gunicorn.conf.py app:app
"""
import os
import multiprocessing

# ── Server socket ──────────────────────────────────────────────────────────
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:5000")

# ── Workers ────────────────────────────────────────────────────────────────
# Rule of thumb: 2-4x CPU cores
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "gthread"        # threaded workers for I/O-bound LLM calls
threads = int(os.environ.get("GUNICORN_THREADS", 4))

# ── Timeouts ───────────────────────────────────────────────────────────────
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))       # 120s for LLM calls
graceful_timeout = 30
keepalive = 5

# ── Request limits ─────────────────────────────────────────────────────────
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# ── Logging ────────────────────────────────────────────────────────────────
accesslog = os.environ.get("GUNICORN_ACCESS_LOG", "-")       # stdout
errorlog = os.environ.get("GUNICORN_ERROR_LOG", "-")         # stderr
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sms'

# ── Process naming ─────────────────────────────────────────────────────────
proc_name = "mulesoft-migrator"

# ── Preload app for faster worker startup ──────────────────────────────────
preload_app = True

# ── Server hooks ───────────────────────────────────────────────────────────
def on_starting(server):
    """Called before the master process is initialized."""
    pass

def post_fork(server, worker):
    """Called after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_exec(server):
    """Called before a new master is forked (during upgrade)."""
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    """Called when a worker receives SIGINT."""
    worker.log.info("Worker received INT or QUIT signal")

def worker_abort(worker):
    """Called when a worker receives SIGABRT."""
    worker.log.info("Worker received SIGABRT signal")
