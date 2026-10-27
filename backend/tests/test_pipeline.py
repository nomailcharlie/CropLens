"""Pytest tests for the CropLens Agent backend.

Run:  cd backend && PYTHONPATH=. python -m pytest -q
"""
import base64
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.samples import make_sample
from app.vision import OPENCV_VERSION, VisionParams, analyze_frame
from app.agent import run_agent
from app.evaluate import generate_case, evaluate_case, run_suite


def test_opencv_is_v5():
    assert OPENCV_VERSION.startswith("5"), f"expected v5, got {OPENCV_VERSION}"


def test_analyze_frame_healthy_has_zero_anomaly():
    data = make_sample("none", seed=3)
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    out = analyze_frame(img, VisionParams())
    assert out.quality.leaf_coverage > 0.05
    assert out.anomaly_area_pct < 0.005


def test_analyze_frame_severe_has_anomaly():
    data = make_sample("severe", seed=5)
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    out = analyze_frame(img, VisionParams())
    assert out.anomaly_area_pct > 0.02
    assert len(out.regions) >= 1


def test_agent_accepts_healthy_and_reviews_severe():
    for sev, expected_action in [("none", "accept"), ("severe", "request_human_review")]:
        data = make_sample(sev, seed=9)
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        r = run_agent(img)
        assert r.final_action == expected_action, f"{sev} -> {r.final_action}"
        assert len(r.trace) >= 2
        assert len(r.passes) >= 1


def test_agent_recaptures_poor_focus():
    data = make_sample("moderate", seed=1)
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    img = cv2.GaussianBlur(img, (51, 51), 12)
    r = run_agent(img)
    assert r.final_action == "request_recapture"


def test_no_leaf_does_not_crash():
    img = np.full((200, 200, 3), 240, np.uint8)  # blank bright image
    r = run_agent(img)
    assert r.final_action == "no_leaf_found"


client = TestClient(app)


def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["opencv_version"].startswith("5")


def test_analyze_endpoint_image():
    data = make_sample("moderate", seed=2)
    r = client.post("/analyze", files={"file": ("leaf.jpg", data, "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["opencv_version"].startswith("5")
    assert "limitations" in body and len(body["limitations"]) > 0
    assert body["annotated_b64"]


def test_analyze_rejects_unsupported_type():
    r = client.post("/analyze", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code in (400, 415)


def test_samples_endpoint_and_analyze():
    r = client.get("/samples")
    assert r.status_code == 200
    items = r.json()
    assert len(items) > 0
    sid = items[0]["id"]
    r2 = client.post(f"/samples/{sid}/analyze")
    assert r2.status_code == 200
    assert r2.json()["ok"] is True


def test_evaluate_endpoint():
    r = client.get("/evaluate")
    assert r.status_code == 200
    body = r.json()
    assert body["n_cases"] > 0
    assert "summary_by_severity" in body


def test_evaluation_suite_runs():
    report = run_suite(seeds=[1])
    assert report["n_cases"] == 16  # 4 severity x 4 degradation x 1 seed
    assert report["opencv_version"].startswith("5")


def test_cors_local_mode_single_origin_header():
    # In "app" mode (default for local), exactly one Access-Control-Allow-Origin
    # header must be present on health, preflight, and a POST — never duplicated.
    # CORSMiddleware only emits headers when an Origin header is present (correct
    # CORS behavior), so we send one on every request.
    ORIGIN = "http://localhost:5173"

    h = client.get("/health", headers={"origin": ORIGIN})
    allow = h.headers.get_list("access-control-allow-origin")
    assert len(allow) == 1, f"health: {allow}"

    pre = client.options(
        "/analyze",
        headers={
            "origin": ORIGIN,
            "access-control-request-method": "POST",
            "access-control-request-headers": "Content-Type",
        },
    )
    assert pre.status_code == 200
    allow_pre = pre.headers.get_list("access-control-allow-origin")
    assert len(allow_pre) == 1, f"preflight: {allow_pre}"

    data = make_sample("mild", seed=4)
    post = client.post(
        "/analyze",
        files={"file": ("leaf.jpg", data, "image/jpeg")},
        headers={"origin": ORIGIN},
    )
    assert post.status_code == 200
    allow_post = post.headers.get_list("access-control-allow-origin")
    assert len(allow_post) == 1, f"post: {allow_post}"
