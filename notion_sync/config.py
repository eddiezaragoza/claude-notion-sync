import json
import os

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "notion-sync-config.json"
)

SYNC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(SYNC_DIR, "notion-sync-state.json")
QUEUE_FILE = os.path.join(SYNC_DIR, "notion-sync-queue.json")
CONFLICTS_FILE = os.path.join(SYNC_DIR, "notion-sync-conflicts.md")
LOG_FILE = os.path.join(SYNC_DIR, "sync.log")

RATE_LIMIT_INTERVAL = 0.4
DEBOUNCE_SECONDS = 60
MAX_BLOCKS_PER_REQUEST = 100
MAX_RETRY_FAILURES = 5


def load_config(config_path=None):
    path = config_path or DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r") as f:
        return json.load(f)


def get_notion_token(config):
    env_var = config.get("notion_token_env_var", "NOTION_API_TOKEN")
    token = os.environ.get(env_var)
    if not token:
        raise EnvironmentError(
            f"Environment variable {env_var} is not set. "
            f"Set it with: export {env_var}=your-notion-integration-token"
        )
    return token
