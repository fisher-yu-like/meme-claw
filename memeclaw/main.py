"""MemeClaw — 网络梗智能检索与分析系统

Usage:
    python -m memeclaw.main search "这很开门"
    python -m memeclaw.main analyze "这很开门"
    python -m memeclaw.main subscribe
    python -m memeclaw.main daily             # 手动触发每日热梗扫描
    python -m memeclaw.main serve         
    python -m memeclaw.main cron              # Start daily intelligence scheduler
"""

import argparse
import asyncio


def main():
    parser = argparse.ArgumentParser(
        prog="memeclaw",
        description="MemeClaw — 网络梗智能检索与分析系统",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # search
    p = sub.add_parser("search", help="搜索梗的基本信息和视频")
    p.add_argument("query", help="梗名或搜索关键词")

    # analyze
    p = sub.add_parser("analyze", help="生成深度文化分析报告")
    p.add_argument("query", help="梗名")

    # subscribe
    sub.add_parser("subscribe", help="订阅每日新梗推送")

    # daily
    sub.add_parser("daily", help="手动触发每日热梗扫描（搜索+LLM判断）")

    # serve
    sub.add_parser("serve", help="启动 HTTP API 服务")

    # cron
    sub.add_parser("cron", help="启动每日情报局定时任务")

    # info
    sub.add_parser("info", help="显示系统配置信息")

    args = parser.parse_args()

    if args.command == "search":
        asyncio.run(_cmd_search(args.query))
    elif args.command == "analyze":
        asyncio.run(_cmd_analyze(args.query))
    elif args.command == "subscribe":
        asyncio.run(_cmd_subscribe())
    elif args.command == "daily":
        asyncio.run(_cmd_daily())
    elif args.command == "serve":
        _cmd_serve()
    elif args.command == "cron":
        asyncio.run(_cmd_cron())
    elif args.command == "info":
        _cmd_info()


async def _cmd_daily():
    """CLI: manually trigger the daily hot meme scan."""
    workflow = await _build_workflow()
    print("正在搜索各平台热梗并交由大模型判断...\n")
    briefing = await workflow.run_daily_intelligence()
    formatted = workflow._get_intelligence().format_briefing(briefing)
    print(formatted)


async def _cmd_search(query: str):
    """CLI: search a meme."""
    workflow = await _build_workflow()

    from memeclaw.models.schemas import WorkflowState
    state = WorkflowState(user_input=query)

    graph = workflow.build_graph()
    result = await graph.ainvoke(state)
    print(result.get("final_response", "无结果"))


async def _cmd_analyze(query: str):
    """CLI: deep analysis."""
    workflow = await _build_workflow()

    from memeclaw.models.schemas import WorkflowState, Intent
    state = WorkflowState(
        user_input=query,
        intent=Intent.DEEP_ANALYSIS,
        user_wants_deep_analysis=True,
    )

    print(f"正在生成「{query}」的深度文化分析报告，请稍候...\n")
    graph = workflow.build_graph()
    result = await graph.ainvoke(state)
    print(result.get("final_response", "生成失败"))


async def _cmd_subscribe():
    """CLI: subscribe to daily briefings."""
    workflow = await _build_workflow()

    from memeclaw.models.schemas import WorkflowState, Intent
    state = WorkflowState(user_input="subscribe", intent=Intent.SUBSCRIBE)

    graph = workflow.build_graph()
    result = await graph.ainvoke(state)
    print(result.get("final_response", "订阅失败"))


def _cmd_serve():
    """Start HTTP API server (FastAPI)."""
    try:
        import uvicorn
        from memeclaw.api import app
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except ImportError:
        print("请安装 uvicorn: pip install uvicorn")


async def _cmd_cron():
    """Run the daily intelligence scheduler."""
    from memeclaw.config import config
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    workflow = await _build_workflow()
    scheduler = AsyncIOScheduler()

    @scheduler.scheduled_job("cron", hour=config.cron_scan_hour, minute=0)
    async def daily_scan():
        briefing = await workflow.run_daily_intelligence()
        formatted = workflow._get_intelligence().format_briefing(briefing)
        print(formatted)

    scheduler.start()
    print(f"梗情报局定时任务已启动，每日 {config.cron_scan_hour}:00 执行扫描。")
    print("按 Ctrl+C 停止。")

    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()


def _cmd_info():
    """Print system configuration."""
    from memeclaw.config import config as cfg
    print("MemeClaw 系统配置")
    print(f"  LLM: {cfg.llm_model}")
    print(f"  判断模型: {cfg.meme_judge_model or cfg.llm_model}")
    print(f"  长文本模型: {cfg.long_context_model}")
    print(f"  搜索引擎: {cfg.search_api}")
    print(f"  视频平台: {', '.join(cfg.video_sources)}")
    print(f"  MongoDB: {cfg.mongo_uri}")
    print(f"  热梗评分阈值: {cfg.hot_score_threshold}")


async def _build_workflow():
    """Build a workflow instance with optional LLM and DB connections."""
    from memeclaw.workflows.master import MemeClawWorkflow
    from memeclaw.storage.database import MemeDatabase

    db = MemeDatabase()
    try:
        await db.connect()
    except Exception:
        db = None  # Run without DB if unavailable

    # Inject OpenAI-compatible LLM client
    llm = None
    try:
        from openai import AsyncOpenAI
        from memeclaw.config import config
        llm = AsyncOpenAI(api_key=config.llm_api_key, base_url=config.llm_base_url)
    except ImportError:
        pass

    return MemeClawWorkflow(llm_client=llm, db=db)


if __name__ == "__main__":
    main()
