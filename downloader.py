import os
import re
import requests
from urllib.parse import urlparse
import html2text
import time
from playwright.sync_api import sync_playwright
from browser_utils import resolve_browser_executable


def _launch_browser(playwright, browser_exe_path, headless):
    launch_kwargs = {"headless": headless}
    resolved_path = resolve_browser_executable(browser_exe_path or "")
    if browser_exe_path and not resolved_path:
        raise FileNotFoundError(f"浏览器路径不存在: {browser_exe_path}")
    if resolved_path:
        launch_kwargs["executable_path"] = resolved_path
    return playwright.chromium.launch(**launch_kwargs)


def _extract_content_html(page):
    return page.evaluate("""
        () => {
            const bodyText = document.body ? document.body.innerText : '';
            const absolutizeImages = (container) => {
                container.querySelectorAll('img').forEach((img) => {
                    // 懒加载属性各家不一：CSDN 用 data-actualsrc，博客园/先知用 data-src/data-original，
                    // 其余站点散见 data-lazy-src / data-echo / data-url / file。逐级回退到 src。
                    const candidate = img.getAttribute('data-actualsrc')
                        || img.getAttribute('data-original-src')
                        || img.getAttribute('data-src')
                        || img.getAttribute('data-original')
                        || img.getAttribute('data-lazy-src')
                        || img.getAttribute('data-echo')
                        || img.getAttribute('data-url')
                        || img.getAttribute('file')
                        || img.getAttribute('src');
                    if (candidate) {
                        try {
                            img.setAttribute('src', new URL(candidate, location.href).href);
                            ['data-actualsrc', 'data-original-src', 'data-src', 'data-original',
                             'data-lazy-src', 'data-echo', 'data-url'].forEach((attr) => img.removeAttribute(attr));
                        } catch (e) {}
                    }
                    // srcset 会让 html2text 生成额外条目，统一清掉，只保留已绝对化的 src
                    if (img.getAttribute('srcset')) {
                        img.removeAttribute('srcset');
                    }
                });
            };

            const cleanupContainer = (container) => {
                container.querySelectorAll([
                    'script',
                    'style',
                    '.login-mark',
                    '.n-reward',
                    '.hljs-button',
                    '.hide-article-box',
                    '.article-search-tip',
                    '.recommend-box',
                    '.template-box',
                    '.passport-login-container',
                    '#treeSkill',
                    '#main-toc',
                    'p[name="tableOfContents"]',
                    // CSDN 文章头尾的元信息/推荐位（选中外层容器时的兜底清理）
                    '.article-info-box',
                    '.article-bar-top',
                    '.article-header-box',
                    '.blog-tags-box',
                    '.slide-content-box',
                    '.toolbox-list',
                    '.hide-preCode-box',
                    '#blogColumnPayAdvert',
                    '.column-group',
                    '.blog-footer-bottom',
                    '.up-time',
                    '.read-count',
                ].join(',')).forEach((element) => {
                    element.remove();
                });
                absolutizeImages(container);
            };

            // 选择器数组已按「具体 -> 宽泛」排序，取第一个正文达标的即可。
            // 早期版本取 innerText 最长的容器，会一路选到最外层 article，
            // 把 CSDN 的「原创/发布时间/阅读量/收录于」头部块一起带进来。
            const pickBestContainer = (selectors) => {
                let fallback = null;
                let fallbackLength = 0;
                for (const selector of selectors) {
                    const node = document.querySelector(selector);
                    if (!node) continue;
                    const textLength = (node.innerText || '').trim().length;
                    if (textLength >= 200) return node;
                    if (textLength > fallbackLength) {
                        fallback = node;
                        fallbackLength = textLength;
                    }
                }
                return fallback;
            };

            const host = location.hostname;
            let post = null;
            let paywalled = false;
            let paywallReason = '';

            if (host.includes('xz.aliyun.com')) {
                post = document.querySelector('.left_container');
                if (!post) return null;

                const clone = post.cloneNode(true);
                ['#news_toolbar', '.detail_info', 'script', 'style'].forEach((selector) => {
                    clone.querySelectorAll(selector).forEach((element) => element.remove());
                });

                ['.detail_share', '.detail_comment', '.reply-list'].forEach((selector) => {
                    const marker = clone.querySelector(selector);
                    if (marker) {
                        let current = marker;
                        while (current) {
                            const next = current.nextElementSibling;
                            current.remove();
                            current = next;
                        }
                    }
                });

                cleanupContainer(clone);
                return {
                    contentHtml: clone.innerHTML,
                    paywalled,
                    paywallReason,
                };
            }

            if (host.includes('csdn.net')) {
                const paywallNode = document.querySelector('.hide-article-box');
                if (paywallNode && /解锁全文|订阅专栏|VIP|付费专栏/.test(paywallNode.innerText || '')) {
                    paywalled = true;
                    paywallReason = (paywallNode.innerText || '').trim().slice(0, 80);
                }
                post = pickBestContainer([
                    '#content_views',
                    '.htmledit_views',
                    '.markdown_views',
                    '#article_content',
                    '.article_content',
                    '.blog-content-box',
                    'article',
                ]);
            } else {
                post = pickBestContainer([
                    '.news-content',
                    '.topic-content',
                    '#article_content',
                    '#cnblogs_post_body',
                    'article',
                ]);
            }

            if (!post) return null;

            const clone = post.cloneNode(true);
            cleanupContainer(clone);

            if (!paywalled && /订阅专栏|解锁全文|VIP免费看|付费专栏/.test(bodyText)) {
                const textLength = (clone.innerText || '').trim().length;
                if (textLength < 4000) {
                    paywalled = true;
                    paywallReason = '页面包含解锁全文提示，当前只能获取预览内容';
                }
            }

            return {
                contentHtml: clone.innerHTML,
                paywalled,
                paywallReason,
            };
        }
    """)


def _extract_title(page):
    return page.evaluate("""
        () => {
            const titleNode = document.querySelector('h1')
                || document.querySelector('.article-title-box')
                || document.querySelector('.article-header-box h1')
                || document.querySelector('.postTitle a')
                || document.querySelector('.left_container h1');
            return titleNode ? titleNode.textContent.trim() : document.title.trim();
        }
    """)


def _build_markdown(article_title, url, content_html):
    h2t = html2text.HTML2Text()
    h2t.body_width = 0
    h2t.mark_code = True
    h2t.ignore_images = False
    h2t.ignore_links = False
    markdown_body = h2t.handle(content_html).strip()

    if len(markdown_body) < 50:
        return ""

    metadata_lines = []
    if article_title:
        metadata_lines.append(f"# {article_title}")
    metadata_lines.append(f"> 来源：{url}")
    metadata_lines.append("")
    metadata_lines.append(markdown_body)
    metadata = "\n".join(metadata_lines).strip() + "\n"
    return metadata.replace("\n\n\n", "\n\n")


def _expand_page_if_needed(page):
    page.evaluate("""
        () => {
            const selectors = [
                'button',
                'a',
                'span',
                '.btn-readmore',
                '#btn-readmore',
                '.hide-article-box',
            ];
            const visited = new Set();
            document.querySelectorAll(selectors.join(',')).forEach((element) => {
                const text = (element.innerText || '').trim();
                if (!text || visited.has(text)) return;
                if (/阅读全文|展开阅读全文|展开更多|点击展开/.test(text)) {
                    visited.add(text);
                    element.click();
                }
            });
        }
    """)
    time.sleep(1)

def _download_and_replace_images(md_text, save_path, article_url):
    base_dir = os.path.dirname(save_path)
    assets_dir_name = "images"
    assets_dir_path = os.path.join(base_dir, assets_dir_name)
    img_counter = [1]

    def internal_download(img_url_raw):
        img_url = img_url_raw.split(' ')[0].strip()
        title_part = (' ' + img_url_raw.split(' ', 1)[1]) if ' ' in img_url_raw else ''
        
        if not img_url.startswith('http'):
            return img_url_raw

        try:
            if not os.path.exists(assets_dir_path):
                os.makedirs(assets_dir_path, exist_ok=True)

            parsed_url = urlparse(img_url)
            ext = os.path.splitext(parsed_url.path)[1]
            if not ext or len(ext) > 5:
                ext = '.png'   
            file_name = f"image_{img_counter[0]}{ext}"
            local_file_path = os.path.join(assets_dir_path, file_name)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": article_url
            }
            response = requests.get(img_url, headers=headers, timeout=15)
            if response.status_code == 200:
                with open(local_file_path, "wb") as f:
                    f.write(response.content)
                img_counter[0] += 1
                return f"./{assets_dir_name}/{file_name}{title_part}"
        except Exception as e:
            print(f"图片下载异常 {img_url}: {e}")
        return img_url_raw

    md_text = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)').sub(
        lambda m: f"![{m.group(1)}]({internal_download(m.group(2).strip())})", 
        md_text
    )
    md_text = re.compile(r'(<img [^>]*src=")([^"]+)("[^>]*>)').sub(
        lambda m: f'{m.group(1)}{internal_download(m.group(2))}{m.group(3)}',
        md_text
    )
    
    return md_text


def _is_verification_page(page):
    """识别 CSDN/博客园 的风控拦截页（安全验证、滑块）。"""
    try:
        title = page.title()
    except Exception:
        return False
    if "安全验证" in title or "Security Verification" in title:
        return True
    try:
        body = page.locator("body").inner_text(timeout=2000)
    except Exception:
        return False
    return "请进行安全验证" in body or "滑动验证" in body


def _scroll_for_lazy_images(page):
    """滚到底再回顶，触发懒加载图片真正写入 src（图文并茂的关键一步）。"""
    try:
        page.evaluate("""
            async () => {
                const step = window.innerHeight;
                const height = document.body.scrollHeight;
                for (let y = 0; y < height; y += step) {
                    window.scrollTo(0, y);
                    await new Promise((r) => setTimeout(r, 200));
                }
                window.scrollTo(0, 0);
            }
        """)
    except Exception:
        pass
    time.sleep(1)


def _download_once(url, final_save_path, browser_exe_path):
    """单次抓取尝试，返回 (ok, detail, retryable)。"""
    with sync_playwright() as p:
        browser = _launch_browser(p, browser_exe_path, headless=True)
        try:
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)

            if _is_verification_page(page):
                # 风控页等几秒有时会自动放行，交给上层重试
                time.sleep(3)
                if _is_verification_page(page):
                    return False, "站点触发安全验证（风控），请降低频率后重试", True

            _expand_page_if_needed(page)
            _scroll_for_lazy_images(page)

            extracted = _extract_content_html(page)
            if not extracted:
                return False, "未能提取正文内容", True

            content_html = extracted.get("contentHtml", "")
            if extracted.get("paywalled"):
                detail = extracted.get("paywallReason") or "目标文章存在付费或解锁限制"
                return False, detail, False

            article_title = _extract_title(page)
            md_text = _build_markdown(article_title, url, content_html)
            if not md_text:
                return False, "正文内容过短", True

            md_text = _download_and_replace_images(md_text, final_save_path, url)
            with open(final_save_path, "w", encoding="utf-8") as f:
                f.write(md_text)
            return True, "", False
        finally:
            browser.close()


def download_as_md(url, save_path, browser_exe_path, retries=3, retry_wait=5.0):
    """下载并转为 Markdown。遇到风控/提取失败会退避重试（默认 3 次）。"""
    try:
        original_dir = os.path.dirname(save_path)
        file_full_name = os.path.basename(save_path)
        pure_name = os.path.splitext(file_full_name)[0]
        article_folder = os.path.join(original_dir, pure_name)
        os.makedirs(article_folder, exist_ok=True)
        final_save_path = os.path.join(article_folder, file_full_name)

        detail = ""
        for attempt in range(1, retries + 1):
            ok, detail, retryable = _download_once(url, final_save_path, browser_exe_path)
            if ok:
                return True, ""
            if not retryable or attempt == retries:
                break
            wait = retry_wait * attempt
            print(f"  第 {attempt} 次失败（{detail}），{wait:.0f}s 后重试")
            time.sleep(wait)
        return False, detail
    except Exception as e:
        print(f"下载出现异常: {e}")
        return False, str(e)