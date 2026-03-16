# System Design Document

## Overview

This is a distributed job management system where a central **server** dispatches work to remote **clients** via WebSocket (SocketIO). Jobs contain one or more tasks, each targeting a specific client. Results flow back through the REST API and are aggregated into completion reports.

## Terminology

| Term | Description |
|------|-------------|
| **Job** | A schedulable unit of work containing one or more tasks |
| **Task** | A single executable action (e.g., `get_hostname`, `ai_test`) assigned to one client |
| **Run** | A recorded execution of a task on a client — stores status, result, and timing |
| **Client** | A remote machine running the client service, identified by its `name` |

## Data Models

### JobStatus

`PENDING` → `RUNNING` → `COMPLETED` / `FAILED` / `CANCELLED`

### Job

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Primary key |
| `name` | str | Human-readable job name |
| `tasks` | List[TaskDefinition] | Tasks to execute |
| `clients` | List[str] | Target client names |
| `status` | JobStatus | Current status |
| `schedule_time` | datetime | When to execute (null = immediate) |
| `cron_expression` | str | Recurring schedule |
| `created_at` / `started_at` / `completed_at` | datetime | Lifecycle timestamps |
| `result` | str | Output on success |
| `error_message` | str | Error details on failure |
| `send_email` | bool | Whether to email on completion |
| `email_recipients` | str | Semicolon-separated email addresses |

Key methods:
- `get_all_clients()` — unique clients from all tasks
- `get_tasks_for_client(name)` — tasks assigned to a specific client

### TaskDefinition

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Task type (maps to registered task class) |
| `client` | str | Target client name |
| `order` | int | Execution order within the job |
| `timeout` | int | Timeout in seconds (default: 300) |
| `args` / `kwargs` | list / dict | Arguments passed to the task |

### Run

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Primary key |
| `job_id` | int | Foreign key to Job |
| `task_name` | str | Which task type was executed |
| `client` | str | Which client executed it |
| `task_order` | int | Execution position |
| `status` | JobStatus | Run outcome |
| `result` | str | Output data |
| `execution_time` | float | Duration in seconds |

### Client

Identified by `name` (not IP). The `get_unique_id()` method returns `self.name`.

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | **Primary identifier** |
| `ip_address` | str | Network address |
| `status` | ClientStatus | ONLINE / OFFLINE / BUSY |
| `last_heartbeat` | datetime | Last health check |
| `current_job_id` | int | Currently executing job |

## Communication Architecture

### Transport Layers

```
Server ──SocketIO──► Client    (task dispatch, ping)
Client ──HTTP POST─► Server    (run status updates, heartbeats)
Browser ──SocketIO─► Server    (real-time UI updates)
```

- **Server → Client**: SocketIO rooms keyed by IP (`client_10_172_21_15`)
- **Client → Server**: REST API (`POST /api/jobs/<id>/runs`)
- **Heartbeats**: HTTP POST from client to server at configurable intervals

### SocketIO Room Mechanism

When a client connects, it joins a room based on its IP address:

```python
# Client side (on connect)
room_name = f"client_{self.local_ip.replace('.', '_')}"
self.sio.emit('join_room', {'room': room_name})

# Server side (on join_room)
join_room(room_name)
```

The scheduler dispatches jobs to this room:

```python
room_name = f"client_{client.ip_address.replace('.', '_')}"
self.socketio.emit('task_dispatch', task_data, room=room_name)
```

### Client Reconnection

The SocketIO client is configured for automatic reconnection after server restarts:

```python
self.sio = socketio.Client(
    reconnection=True,
    reconnection_attempts=0,      # unlimited
    reconnection_delay=2,         # initial delay: 2 seconds
    reconnection_delay_max=30,    # max delay: 30 seconds (exponential backoff)
)
```

On reconnect, the client automatically re-joins its room via the `connect` event handler, so task dispatches resume without requiring a client service restart.

## Job Lifecycle

### 1. Creation

```
Web UI / API  →  POST /api/jobs  →  Database (status: PENDING)
```

### 2. Scheduling & Dispatch

The scheduler runs `_check_pending_tasks()` every **10 seconds**:

1. Queries all jobs with `status == PENDING`
2. Checks if execution time has arrived (immediate, scheduled, or cron)
3. Verifies all required clients are available (status: ONLINE)
4. Sets job status to `RUNNING`
5. Emits `task_dispatch` to each client's SocketIO room

```python
# Dispatch payload per client
task_data = {
    'task_id': job.id,
    'name': job.name,
    'client_name': client.name,
    'tasks': [t.to_dict() for t in client_tasks]
}
```

### 3. Execution (Client Side)

On receiving `task_dispatch`, the client:

1. Spawns a thread to execute the job's tasks sequentially
2. For each task, POSTs run status to `POST /api/jobs/<id>/runs`:
   - `status: running` — task started
   - `status: completed` — task finished with result
   - `status: failed` — task failed with error

### 4. Completion Detection (Server Side)

When the server receives a completed/failed run update:

```
on_run_completion()
  └─► _check_job_completion(job_id)
        ├─ Acquires completion lock
        ├─ Checks if job_id already being processed (dedup)
        ├─ For each (task, client) pair:
        │    └─ Queries runs, checks latest status
        └─ If all finished → adds to _processing_jobs, returns True
  └─► _process_job_completion(job_id)  [background thread]
        ├─ Collects results per client
        ├─ Sets final status: COMPLETED or FAILED
        ├─ Generates HTML report
        ├─ Sends email notification (if configured)
        ├─ Caches results to task_results table
        ├─ Emits 'task_completed' WebSocket event
        └─ Removes job_id from _processing_jobs
```

### 5. Stuck Job Recovery

On server startup, the scheduler calls `_recover_stuck_jobs()`:

1. Finds all jobs with `status == RUNNING`
2. For each, checks if all task/client pairs have a finished run
3. If all finished → marks job as `COMPLETED` or `FAILED`

This handles the case where the server restarted while a job was completing and the status update was lost.

## Race Condition Protection

### Problem

Multiple SocketIO connections from the same client can cause duplicate dispatches. The `task_executed` endpoint was setting `status = RUNNING` unconditionally, which could overwrite `COMPLETED` if a late acknowledgement arrived after the completion thread finished.

### Solution

The `task_executed` endpoint only updates status when the job is still `PENDING`:

```python
if task.status == JobStatus.PENDING:
    task.status = JobStatus.RUNNING
    task.started_at = datetime.now()
    database.update_job(task)
```

The completion flow uses a lock and deduplication set (`_processing_jobs`) to prevent double-processing.

## Scheduler Intervals

| Job | Interval | Purpose |
|-----|----------|---------|
| `_check_pending_tasks` | 10 seconds | Dispatch pending jobs |
| `_cleanup_offline_clients` | 30 seconds | Mark stale clients offline |
| `_recover_stuck_jobs` | On startup | Fix jobs stuck in RUNNING |
