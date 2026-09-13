#!/usr/bin/env python3
"""博客下载助手 · 无 GUI 批量抓取入口。

按专题预设（topics.json）批量检索并导出 图文并茂 的 Markdown 知识库，
适合在断网比赛前批量囤文档，或在服务器上定时同步。

示例：
    python cli.py --list-topics
    python cli.py --topic pwn-patch-binary --pages 2 --limit 12 --out knowledge
    python cli.py --keyword "patchelf rpath" --sites CSDN --limit 5 --out knowledge
"""
import argparse
import os
import sys
import time

from browser_utils import detect_browser_executable, resolve_browser_executable
from downloader import download_as_md
from puller import concurrent_search
from topics import filter_results, load_topics

DEFAULT_SITES = ["CSDN", "先知社区"]


def build_parser():
    parser = argparse.ArgumentParser(
        description="博客下载助手 · 批量抓取（专题预设见 topics.json）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--list-topics", action="store_true", help="列出所有专题预设后退出")
    parser.add_argument("--topic", help="专题 id，支持逗号分隔多个，或写 all 全量（配合 --list-topics 查看）")
    parser.add_argument("--all-topics", action="store_true", help="等价于 --topic all，全量抓取所有专题")
    parser.add_argument("--keyword", help="自定义关键词；给了它就不走专题的关键词列表")
    parser.add_argument("--pages", type=int, default=1, help="每个关键词搜索页数（默认 1）")
    parser.add_argument("--limit", type=int, default=10, help="最多下载篇数（默认 10）")
    parser.add_argument("--out", default="knowledge", help="导出根目录（默认 ./knowledge）")
    parser.add_argument("--sites", default=",".join(DEFAULT_SITES),
                        help="平台白名单，逗号分隔，可选 CSDN,博客园,先知社区（默认 CSDN,先知社区）")
    parser.add_argument("--browser", default="", help="浏览器可执行文件路径；留空自动检测，再留空用 Playwright Chromium")
    parser.add_argument("--show-browser", action="store_true",
                        help="以有头模式搜索（博客园滑块验证需要）；默认 headless")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="每篇下载之间的间隔秒数，降低被风控概率（默认 3）")
    parser.add_argument("--retries", type=int, default=3,
                        help="单篇遇到风控/提取失败的重试次数（默认 3）")
    parser.add_argument("--dry-run", action="store_true", help="只搜索并打印命中列表，不下载")
    return parser


def print_topics():
    topics = load_topics()
    print("可用专题预设：\n")
    for tid, topic in topics.items():
        print(f"  {tid}")
        print(f"    名称：{topic['name']}")
        print(f"    说明：{topic.get('description', '')}")
        print(f"    关键词：{' / '.join(topic['keywords'])}")
        print()
    print("用法：python cli.py --topic <id> --pages 2 --limit 10 --out knowledge")


def resolve_browser(browser_arg):
    if browser_arg:
        resolved = resolve_browser_executable(browser_arg)
        if not resolved:
            sys.exit(f"浏览器路径无效：{browser_arg}")
        return resolved
    return detect_browser_executable()


def collect_results(keywords, pages, sites, browser, headless, topic):
    """逐个关键词检索，按专题规则过滤后全局去重。"""
    merged = []
    for index, keyword in enumerate(keywords, start=1):
        print(f"[{index}/{len(keywords)}] 搜索：{keyword}")
        try:
            results = concurrent_search(
                keyword, pages, browser, sites=sites, headless=headless,
            )
        except Exception as exc:
            print(f"    搜索失败：{exc}")
            continue
        kept = filter_results(results, topic) if topic else results
        print(f"    命中 {len(results)} 条，过滤后 {len(kept)} 条")
        merged.extend(kept)

    seen = set()
    unique = []
    for item in merged:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        unique.append(item)
    # 打分命中的排前面；没有专题时（自定义关键词）保持平台默认顺序
    unique.sort(key=lambda item: item.get("score", 0), reverse=True)
    return unique


def write_index(out_dir, topic_name, entries, failures):
    index_path = os.path.join(out_dir, "index.md")
    lines = [f"# {topic_name}", "", f"> 由 博客下载助手 cli.py 生成，共 {len(entries)} 篇", ""]
    for item in entries:
        rel = item["file"]
        lines.append(f"- [{item['title']}]({rel}) —— {item['site']}")
    if failures:
        lines += ["", "## 未成功抓取", ""]
        for title, reason in failures:
            lines.append(f"- {title} —— {reason}")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    return index_path


def process_topic(topic_id, topic_name, keywords, topic, args, sites, browser, headless):
    """处理单个专题：搜索 -> 打分过滤 -> 下载 -> 写索引。返回 (entries, failures)。"""
    print("\n" + "=" * 72)
    print(f"专题：{topic_name}（{topic_id}）")
    print("=" * 72)

    results = collect_results(keywords, args.pages, sites, browser, headless, topic)
    if not results:
        print("没有命中任何文章，可换关键词或加 --show-browser 过验证码。")
        return [], []

    print(f"\n去重后共 {len(results)} 篇，准备下载前 {min(args.limit, len(results))} 篇\n")
    if args.dry_run:
        for item in results[: args.limit]:
            score = item.get("score")
            score_text = f"  [score {score}]" if score is not None else ""
            print(f"  [{item['site']}] {item['title']}{score_text}")
            print(f"      {item['url']}")
        return [], []

    out_dir = os.path.join(args.out, topic_id)
    os.makedirs(out_dir, exist_ok=True)

    entries = []
    failures = []
    total = min(args.limit, len(results))
    for index, item in enumerate(results[: args.limit], start=1):
        print(f"[{index}/{total}] 下载：{item['title'][:60]}")
        save_path = os.path.join(out_dir, f"{item['title']}.md")
        started = time.time()
        try:
            ok, detail = download_as_md(item["url"], save_path, browser,
                                        retries=args.retries, retry_wait=args.delay + 2)
        except Exception as exc:
            ok, detail = False, str(exc)
        if ok:
            article_dir = os.path.join(out_dir, os.path.splitext(os.path.basename(save_path))[0])
            entries.append({
                "title": item["title"],
                "site": item["site"],
                "file": f"{os.path.basename(article_dir)}/{os.path.basename(save_path)}",
            })
            img_dir = os.path.join(article_dir, "images")
            img_count = len(os.listdir(img_dir)) if os.path.isdir(img_dir) else 0
            print(f"    OK（{time.time() - started:.1f}s，图片 {img_count} 张）")
        else:
            failures.append((item["title"], detail or "未知原因"))
            print(f"    失败：{detail}")
        if index < total and args.delay > 0:
            time.sleep(args.delay)

    index_path = write_index(out_dir, topic_name, entries, failures)
    print(f"\n专题「{topic_name}」完成：成功 {len(entries)} 篇，失败 {len(failures)} 篇")
    print(f"索引：{index_path}")
    return entries, failures


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.list_topics:
        print_topics()
        return 0

    if not args.all_topics and not args.topic and not args.keyword:
        build_parser().print_help()
        return 2

    sites = [s.strip() for s in args.sites.split(",") if s.strip()]
    browser = resolve_browser(args.browser)
    headless = not args.show_browser

    print(f"平台：{', '.join(sites)}")
    print(f"浏览器：{browser or 'Playwright 自带 Chromium'}")
    print(f"模式：{'有头' if args.show_browser else 'headless'}"
          f"{'（dry-run，不下载）' if args.dry_run else ''}")

    # --topic 支持逗号分隔多个 / all；--all-topics 是 all 的别名
    all_topics = load_topics()
    topic_ids = []
    if args.all_topics or (args.topic and args.topic.strip().lower() == "all"):
        topic_ids = list(all_topics.keys())
    elif args.topic:
        topic_ids = [tid.strip() for tid in args.topic.split(",") if tid.strip()]
    else:
        topic_ids = []  # 仅自定义关键词

    if len(topic_ids) > 1 or (topic_ids and not args.dry_run):
        print(f"待处理专题数：{len(topic_ids)}")

    if not topic_ids:
        # 纯自定义关键词：topic=None 表示不套专题打分过滤，命中即收录
        entries, failures = process_topic("custom", args.keyword, [args.keyword], None,
                                         args, sites, browser, headless)
        print(f"\n知识库根目录：{os.path.abspath(args.out)}")
        return 0 if entries or args.dry_run else 1

    summary = []
    for tid in topic_ids:
        if tid not in all_topics:
            print(f"跳过未知专题 id：{tid}")
            continue
        topic = all_topics[tid]
        keywords = topic["keywords"] if not args.keyword else [args.keyword]
        entries, failures = process_topic(tid, topic["name"], keywords, topic,
                                         args, sites, browser, headless)
        summary.append((topic["name"], len(entries), len(failures)))

    if len(summary) > 1:
        print("\n" + "=" * 72)
        print("全量抓取汇总")
        print("=" * 72)
        total_e = total_f = 0
        for name, e, f in summary:
            total_e += e
            total_f += f
            print(f"  {name}：成功 {e} 篇，失败 {f} 篇")
        print(f"\n合计：成功 {total_e} 篇，失败 {total_f} 篇")

    print(f"\n知识库根目录：{os.path.abspath(args.out)}")
    print("用 Obsidian / Typora 打开该目录即可离线检索（每篇一个文件夹，图片在 images/）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
