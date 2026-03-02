# Self-healing CI demo (REST API)

This project demonstrates a **self-healing continuous integration pipeline** around a small FastAPI REST API.

The pipeline:

- Starts the API in CI
- Waits for `/health` with retries and backoff
- Restarts the API if it does not become healthy
- Runs tests that can **re-run transiently failing cases**

## Tech stack

| Layer        | Technology |
|-------------|------------|
| Language    | Python 3.11+ |
| API framework | [FastAPI](https://fastapi.tiangolo.com/) |
| ASGI server | [Uvicorn](https://www.uvicorn.org/) |
| HTTP client (tests + health checks) | [httpx](https://www.python-httpx.org/) |
| Testing     | [pytest](https://pytest.org/), [pytest-rerunfailures](https://pypi.org/project/pytest-rerunfailures/) |
| CI/CD       | [GitHub Actions](https://docs.github.com/en/actions) |

## Project layout

```
self-healing/
  app/
    main.py          # FastAPI application
  ci/
    run_ci.py        # Self-healing CI runner (used locally and in GitHub Actions)
  tests/
    test_api.py      # REST API tests (health, item, unstable)
  requirements.txt
  logs/              # Created at runtime
    server.log
    tests.log
    health_start_count
  README.md
```

## Local usage

### 1. Create and activate a virtualenv (recommended)

```bash
cd /path/to/cursor-projects
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r self-healing/requirements.txt
```

### 3. Run the self-healing CI script

```bash
python self-healing/ci/run_ci.py
```

This will:

- Start the FastAPI server (uvicorn)
- Poll `http://127.0.0.1:8000/health` until 200 (with restarts and backoff if the server does not come up)
- Run pytest against `self-healing/tests`
- Write logs to `self-healing/logs/server.log` and `self-healing/logs/tests.log`

### Simulating failed health and server restart

On the **first** server start, `/health` returns **503** for 36 seconds (longer than the runner’s 30s health timeout), so:

1. Runner starts the server (attempt 1).
2. Health checks get 503 for 30s → timeout → runner stops the server and backs off.
3. Runner starts the server again (attempt 2).
4. `/health` returns 200 immediately → health passes → tests run.

The “first start” is tracked in `self-healing/logs/health_start_count`. To see the failed-health-and-restart behavior again:

```bash
rm -f self-healing/logs/health_start_count
python self-healing/ci/run_ci.py
```

## API endpoints

| Method | Path            | Description |
|--------|-----------------|-------------|
| GET    | `/health`       | Always 200 when healthy; 503 for first 36s on first-ever start (demo). |
| GET    | `/items/{id}`   | Returns `{"item_id": N, "name": "item-N"}`. |
| GET    | `/unstable`    | Fails the first N calls (env `UNSTABLE_FAIL_FIRST_N`, default 3), then 200. Used to demonstrate test reruns. |

## GitHub Actions workflow

The workflow `.github/workflows/self-healing-ci.yml`:

- Runs on every push and pull request
- Checks out the repo, sets up Python 3.11, installs `self-healing/requirements.txt`
- Runs `python self-healing/ci/run_ci.py`
- Uploads `self-healing/logs/server.log` and `self-healing/logs/tests.log` as artifacts (always, for debugging)

## Steps to check in to GitHub

### 1. Create a new repository on GitHub

- Go to [github.com/new](https://github.com/new).
- Choose a name (e.g. `self-healing-demo`), leave it empty (no README, no .gitignore).
- Copy the repo URL (e.g. `https://github.com/YOUR_USERNAME/self-healing-demo.git`).

### 2. From your project root, commit and push

From the folder that contains `self-healing/` and `.github/` (e.g. `cursor-projects/`):

```bash
cd /path/to/cursor-projects

# If this folder is not yet a git repo:
git init

# Stage everything (including .github/workflows and self-healing/)
git add .
git commit -m "Add self-healing CI demo"

# Add your GitHub repo as remote and push
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` and `YOUR_REPO` with your GitHub username and repository name.

### 3. View the workflow run

- Open your repo on GitHub.
- Click the **Actions** tab.
- You should see a run for **“Self-healing CI (REST API)”** from the push.
- Click the run to see each step (Checkout, Set up Python, Install dependencies, Run self-healing CI runner, Upload logs).

### 4. Download logs (optional)

- In the same run page, scroll to **Artifacts**.
- Download **self-healing-logs** (a zip with `server.log` and `tests.log`) to inspect server and test output.

### 5. Re-run or trigger on PR

- Every new **push** or **pull request** will trigger the same workflow.
- To re-run a past workflow: open the run → **Re-run all jobs**.
