"""Python SDK for Think Box AI API.

Usage:
    from thinkbox import Client
    client = Client("http://localhost:8000")
    jobs = client.jobs.list()
    client.jobs.create(intent="Research DOGI", hat="researcher")
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import urllib.request
import urllib.error


class APIError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"API {status}: {message}")


@dataclass
class Job:
    id: str
    intent: str
    hat: str
    state: str
    inputs: dict
    plan: list
    execution: list
    artifacts: list
    evaluation: dict
    cost: dict


class JobsAPI:
    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _request(self, method: str, path: str, data: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise APIError(e.code, e.read().decode())

    def list(self, state: str | None = None, limit: int = 50) -> list[Job]:
        params = f"?limit={limit}"
        if state:
            params += f"&state={state}"
        result = self._request("GET", f"/api/v1/jobs{params}")
        return [Job(**j) for j in result.get("jobs", [])]

    def get(self, job_id: str) -> Job:
        return Job(**self._request("GET", f"/api/v1/jobs/{job_id}"))

    def create(self, intent: str, hat: str = "researcher", inputs: dict | None = None) -> Job:
        data = {"intent": intent, "hat": hat, "inputs": inputs or {}}
        return Job(**self._request("POST", "/api/v1/jobs", data))

    def run(self, job_id: str) -> dict:
        return self._request("POST", f"/api/v1/jobs/{job_id}/run")

    def delete(self, job_id: str) -> dict:
        return self._request("DELETE", f"/api/v1/jobs/{job_id}")


class FindingsAPI:
    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _request(self, method: str, path: str) -> dict:
        url = f"{self.base_url}{path}"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(url, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def list(self) -> list[str]:
        return self._request("GET", "/api/v1/findings").get("findings", [])

    def get(self, name: str) -> str:
        return self._request("GET", f"/api/v1/findings/{name}").get("content", "")


class Client:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = ""):
        self.base_url = base_url
        self.api_key = api_key
        self.jobs = JobsAPI(base_url, api_key)
        self.findings = FindingsAPI(base_url, api_key)

    def health(self) -> dict:
        req = urllib.request.Request(f"{self.base_url}/health")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def metrics(self) -> dict:
        req = urllib.request.Request(f"{self.base_url}/metrics")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
