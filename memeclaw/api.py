"""FastAPI server for MemeClaw — exposes REST API endpoints."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import asyncio
import json
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
from pydantic import BaseModel

from memeclaw.models.schemas import (
    AnthropologistReport,
    MemeEncyclopediaEntry,
    VideoHunterResult,
    WorkflowState,
    Intent,
)
from memeclaw.workflows.master import MemeClawWorkflow
from memeclaw.storage.database import MemeDatabase


workflow: MemeClawWorkflow = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global workflow
    db = MemeDatabase()
    try:
        await db.connect()
    except Exception:
        db = None

    llm = None
    try:
        from openai import AsyncOpenAI
        from memeclaw.config import config
        llm = AsyncOpenAI(api_key=config.llm_api_key, base_url=config.llm_base_url)
    except Exception:
        pass

    workflow = MemeClawWorkflow(llm_client=llm, db=db)
    yield


app = FastAPI(
    title="MemeClaw API",
    description="网络梗智能检索与分析系统",
    version="1.0.0",
    lifespan=lifespan,
)


class SearchResponse(BaseModel):
    meme_name: str
    encyclopedia: Optional[MemeEncyclopediaEntry] = None
    videos: Optional[VideoHunterResult] = None
    analysis: Optional[AnthropologistReport] = None
    error: Optional[str] = None
    suggestions: list[str] = []


class SubscribeRequest(BaseModel):
    user_id: str
    webhook_url: Optional[str] = None
    email: Optional[str] = None


@app.get("/search", response_model=SearchResponse)
async def search_meme(q: str = Query(..., description="梗名或搜索关键词")):
    """Search for a meme by name. Returns encyclopedia data + videos."""
    state = WorkflowState(user_input=q)
    graph = workflow.build_graph()
    result = await graph.ainvoke(state)
    final = WorkflowState(**result) if isinstance(result, dict) else state
    return SearchResponse(
        meme_name=final.meme_name or q,
        encyclopedia=final.encyclopedia_result,
        videos=final.video_result,
        error=final.error,
        suggestions=final.suggestions,
    )


@app.get("/analyze", response_model=AnthropologistReport)
async def analyze_meme(q: str = Query(..., description="梗名")):
    """Generate a deep cultural analysis report for a meme."""
    state = WorkflowState(
        user_input=q,
        intent=Intent.DEEP_ANALYSIS,
        user_wants_deep_analysis=True,
    )
    graph = workflow.build_graph()
    result = await graph.ainvoke(state)
    final = WorkflowState(**result) if isinstance(result, dict) else state
    if final.error and not final.analysis_result:
        raise HTTPException(500, detail=final.error)
    if final.analysis_result is None:
        # Include the error if set (surfaced from workflow)
        detail = final.error or "分析生成失败，请稍后重试"
        raise HTTPException(500, detail=detail)
    return final.analysis_result


@app.post("/subscribe")
async def subscribe(req: SubscribeRequest):
    """Subscribe to daily new-meme briefings."""
    if workflow.db is not None and workflow.db.db is not None:
        await workflow.db.add_subscriber(req.user_id, req.webhook_url, req.email)
    else:
        # Fallback: local JSON file when MongoDB is unavailable
        import json as _json
        subs_path = Path(__file__).parent.parent / "data" / "subscriptions.json"
        subs_path.parent.mkdir(parents=True, exist_ok=True)
        subs = []
        if subs_path.exists():
            try:
                subs = _json.loads(subs_path.read_text(encoding="utf-8"))
            except Exception:
                subs = []
        subs.append({
            "user_id": req.user_id,
            "webhook_url": req.webhook_url,
            "email": req.email,
            "subscribed_at": datetime.now().isoformat(),
        })
        subs_path.write_text(_json.dumps(subs, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "message": "订阅成功"}


@app.get("/daily-briefing")
async def daily_briefing(response: Response):
    """Trigger a daily hot meme scan: search platforms + LLM judge."""
    response.headers.update(_NO_CACHE)
    try:
        briefing = await workflow.run_daily_intelligence()
        # Generate formatted markdown for frontend rendering
        formatted_md = workflow._get_intelligence().format_briefing(briefing)
        return {
            "scan_date": briefing.scan_date.isoformat(),
            "briefing": formatted_md,
            "summary": briefing.summary,
            "confirmed_hot_memes": [
                {
                    "keyword": m.keyword,
                    "definition": m.definition,
                    "source_platforms": m.source_platforms,
                    "hot_score": m.hot_score,
                    "is_hot": m.is_hot,
                    "judge_reason": m.judge_reason,
                    "urls": m.urls,
                }
                for m in briefing.confirmed_hot_memes
            ],
            "candidates": [
                {
                    "keyword": m.keyword,
                    "definition": m.definition,
                    "source_platforms": m.source_platforms,
                    "hot_score": m.hot_score,
                    "is_hot": m.is_hot,
                    "judge_reason": m.judge_reason,
                    "urls": m.urls,
                }
                for m in briefing.candidates
            ],
            "candidates_count": len(briefing.candidates),
            "confirmed_count": len(briefing.confirmed_hot_memes),
        }
    except Exception as e:
        raise HTTPException(500, detail=f"梗情报获取失败: {e}")


@app.get("/daily-briefing/stream")
async def daily_briefing_stream():
    """Stream daily hot meme scan progress via NDJSON (newline-delimited JSON).

    Each line is a JSON object: {"type":"progress","message":"...","step":"..."}
    Final line is:         {"type":"result",...briefing fields...}
    On error:              {"type":"error","message":"..."}
    """
    queue: asyncio.Queue = asyncio.Queue()

    async def on_progress(message: str, step: str):
        await queue.put(json.dumps({"type": "progress", "message": message, "step": step}, ensure_ascii=False))

    async def run_scan():
        try:
            briefing = await workflow.run_daily_intelligence(progress_callback=on_progress)
            formatted_md = workflow._get_intelligence().format_briefing(briefing)
            result = {
                "type": "result",
                "scan_date": briefing.scan_date.isoformat(),
                "briefing": formatted_md,
                "summary": briefing.summary,
                "confirmed_hot_memes": [
                    {
                        "keyword": m.keyword,
                        "definition": m.definition,
                        "source_platforms": m.source_platforms,
                        "hot_score": m.hot_score,
                        "is_hot": m.is_hot,
                        "judge_reason": m.judge_reason,
                        "urls": m.urls,
                    }
                    for m in briefing.confirmed_hot_memes
                ],
                "candidates": [
                    {
                        "keyword": m.keyword,
                        "definition": m.definition,
                        "source_platforms": m.source_platforms,
                        "hot_score": m.hot_score,
                        "is_hot": m.is_hot,
                        "judge_reason": m.judge_reason,
                        "urls": m.urls,
                    }
                    for m in briefing.candidates
                ],
                "candidates_count": len(briefing.candidates),
                "confirmed_count": len(briefing.confirmed_hot_memes),
            }
            await queue.put(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            await queue.put(json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False))

    async def generate():
        task = asyncio.create_task(run_scan())
        while True:
            line = await queue.get()
            yield line + "\n"
            if '"type": "result"' in line or '"type": "error"' in line:
                break
        await task

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers=_NO_CACHE,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "memeclaw"}


@app.get("/", include_in_schema=False)
async def root():
    """Serve index.html with no-cache headers to prevent 304."""
    index_path = Path(__file__).parent / "static" / "index.html"
    if not index_path.is_file():
        raise HTTPException(404, "index.html not found")
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"), headers=_NO_CACHE)


# Mount static frontend — must be after all API routes
_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
