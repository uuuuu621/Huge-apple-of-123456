# -*- coding: utf-8 -*-
"""
舆情分析工作台 —— Flask 后端。

提供：
  GET  /                           工作台前端页面
  POST /api/task                   创建任务（返回 task_id）
  GET  /api/task/<id>/events       任务进度 SSE 流
  GET  /api/task/<id>/result       任务结果
  GET  /files/<rel_path>           下载/预览归档报告文件
"""
import json
import os
import queue
import threading
import uuid

from flask import Flask, Response, jsonify, request, send_from_directory

import config
from core import pipeline

app = Flask(__name__, static_folder="workbench", static_url_path="")

TASKS = {}
LOCK = threading.Lock()


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/task", methods=["POST"])
def create_task():
    cfg = request.get_json(force=True) or {}
    task_id = uuid.uuid4().hex[:12]
    q = queue.Queue()
    with LOCK:
        TASKS[task_id] = {"queue": q, "status": "running", "result": None, "error": None, "config": cfg}

    def _emit(event, **data):
        q.put({"event": event, **data})

    def _run():
        try:
            result = pipeline.run_pipeline(cfg, _emit)
            with LOCK:
                TASKS[task_id]["status"] = "done"
                TASKS[task_id]["result"] = result
        except Exception as e:
            import traceback
            traceback.print_exc()
            _emit("error", message=str(e))
            with LOCK:
                TASKS[task_id]["status"] = "error"
                TASKS[task_id]["error"] = str(e)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/task/<task_id>/events")
def task_events(task_id):
    with LOCK:
        t = TASKS.get(task_id)
    if t is None:
        return jsonify({"error": "任务不存在"}), 404

    def gen():
        q = t["queue"]
        while True:
            try:
                item = q.get(timeout=30)
            except queue.Empty:
                yield "event: ping\ndata: {}\n\n"
                continue
            yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"
            if item.get("event") in ("done", "error"):
                break

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/task/<task_id>/result")
def task_result(task_id):
    with LOCK:
        t = TASKS.get(task_id)
    if t is None:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify({"status": t["status"], "result": t["result"], "error": t["error"]})


@app.route("/files/<path:path>")
def serve_file(path):
    base = os.path.abspath(config.REPORT_DIR)
    target = os.path.abspath(os.path.join(base, path))
    if not target.startswith(base + os.sep) and target != base:
        return "forbidden", 403
    return send_from_directory(base, path)


if __name__ == "__main__":
    print("=" * 56)
    print("  舆情分析工作台已启动")
    print("  打开浏览器访问：http://127.0.0.1:5000")
    print("=" * 56)
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
