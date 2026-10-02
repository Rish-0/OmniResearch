"""Test that Docker compose files never mount docker.sock into app containers."""

from pathlib import Path

import yaml


def test_compose_no_docker_sock() -> None:
    """Verify compose file has no docker.sock volume mounts."""
    compose_file = Path("infra/docker/compose.yml")
    assert compose_file.exists(), "compose.yml must exist"

    content = compose_file.read_text()
    assert "docker.sock" not in content, "docker.sock must NEVER be mounted into any compose service!"

    data = yaml.safe_load(content)
    for service_name, service_cfg in data.get("services", {}).items():
        volumes = service_cfg.get("volumes", [])
        for vol in volumes:
            vol_str = str(vol)
            assert "docker.sock" not in vol_str, (
                f"Service '{service_name}' mounts docker.sock ({vol_str})"
            )
