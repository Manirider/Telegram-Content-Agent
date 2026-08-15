#!/usr/bin/env python3
"""Health check script for container."""
import sys
import urllib.request
import urllib.error
import json


def check_health(host: str = "localhost", port: int = 8080) -> bool:
    """Check application health."""
    url = f"http://{host}:{port}/health"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get("status") == "healthy"
    except urllib.error.URLError:
        pass
    except json.JSONDecodeError:
        pass
    except Exception:
        pass
    
    return False


def check_ready(host: str = "localhost", port: int = 8080) -> bool:
    """Check application readiness."""
    url = f"http://{host}:{port}/ready"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get("status") == "ready"
    except urllib.error.URLError:
        pass
    except json.JSONDecodeError:
        pass
    except Exception:
        pass
    
    return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--check", choices=["health", "ready"], default="health")
    args = parser.parse_args()
    
    if args.check == "health":
        healthy = check_health(args.host, args.port)
    else:
        healthy = check_ready(args.host, args.port)
    
    if healthy:
        print(f"{args.check.capitalize()} check passed")
        sys.exit(0)
    else:
        print(f"{args.check.capitalize()} check failed")
        sys.exit(1)