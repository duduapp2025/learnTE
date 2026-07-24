#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用 Playwright 抓取 The Economist 完整文章内容
"""

import os
import sys
import json
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def get_article_links(page, edition_url):
    """
    从周刊页面获取所有文章链接 - 通用版，尝试多种提取策略
    """
    print(f"正在访问: {edition_url}")
    
    try:
        page.goto(edition_url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
    except Exception as e:
        print(f"页面加载超时，尝试继续: {e}")
        try:
            page.goto(edition_url, timeout=30000, wait_until="commit")
        except:
            print("页面加载完全失败，跳过")
            return []
    
    try:
        page.evaluate("document.querySelectorAll('[class*=\"cookie\"], [class*=\"consent\"]').forEach(el => el.remove())")
    except:
        pass
    
    # ===== 方法1：从 __NEXT_DATA__ 提取 =====
    print("正在从 __NEXT_DATA__ 提取文章链接...")
    try:
        next_data = page.evaluate('''
            () => {
                const script = document.getElementById('__NEXT_DATA__');
                if (script) {
                    try {
                        return JSON.parse(script.innerText);
                    } catch(e) {}
                }
                return null;
            }
        ''')
        if next_data:
            articles = []
            # 尝试不同的数据路径
            try:
                articles = next_data['props']['pageProps']['content']['articles']
            except:
                try:
                    articles = next_data['props']['pageProps']['content']['components']
                except:
                    try:
                        articles = next_data['props']['pageProps']['articles']
                    except:
                        pass
            
            if articles:
                links = []
                for article in articles:
                    title = article.get('headline', '') or article.get('title', '')
                    url = article.get('url', '')
                    if url and title:
                        if url.startswith('/'):
                            url = 'https://www.economist.com' + url
                        if not url.startswith('http'):
                            url = 'https://www.economist.com' + url
                        links.append({'title': title, 'url': url})
                if links:
                    print(f"从 JSON 提取到 {len(links)} 篇文章")
                    return links
    except Exception as e:
        print(f"从 JSON 提取失败: {e}")
    
    # ===== 方法2：从页面 HTML 链接中提取 =====
    print("正在从页面 HTML 中提取文章链接...")
    raw_links = page.evaluate('''
        () => {
            const results = [];
            const baseUrl = 'https://www.economist.com';
            const allLinks = document.querySelectorAll('a[href]');
            const seen = new Set();
            
            allLinks.forEach(a => {
                let href = a.getAttribute('href');
                if (!href) return;
                
                if (href.startsWith('#') || href.includes('javascript:') || 
                    href.includes('/podcast/') || href.includes('/video/') ||
                    href.includes('/search') || href.includes('/login')) {
                    return;
                }
                
                let fullUrl = href;
                if (href.startsWith('/')) {
                    fullUrl = baseUrl + href;
                } else if (!href.startsWith('http')) {
                    return;
                }
                
                if (fullUrl.match(/https?:\\/\\/www\\.economist\\.com\\/\\d{4}\\/\\d{2}\\/\\d{2}\\//)) {
                    if (!seen.has(fullUrl)) {
                        seen.add(fullUrl);
                        const title = a.innerText.trim().replace(/\\s+/g, ' ');
                        if (title && title.length > 15) {
                            results.push({ title: title, url: fullUrl });
                        }
                    }
                }
            });
            return results;
        }
    ''')
    
    # 去重
    unique_links = []
    seen_urls = set()
    for link in raw_links:
        if link['url'] not in seen_urls:
            seen_urls.add(link['url'])
            unique_links.append(link)
    
    print(f"从页面 HTML 中找到 {len(unique_links)} 篇文章链接")
    for i, link in enumerate(unique_links[:5]):
        print(f"  示例链接 {i+1}: {link['title'][:50]}... -> {link['url']}")
    
    return unique_links


def fetch_article_content(page, url):
    """
    使用 Playwright 抓取单篇文章的正文内容
    """
    print(f"  抓取文章: {url}")
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        
        try:
            page.evaluate("document.querySelectorAll('[class*=\"cookie\"], [class*=\"consent\"]').forEach(el => el.remove())")
        except:
            pass
        
        article_data = page.evaluate('''
            () => {
                const nextData = document.getElementById('__NEXT_DATA__');
                let jsonData = null;
                if (nextData) {
                    try {
                        jsonData = JSON.parse(nextData.innerText);
                    } catch(e) {}
                }
                
                let title = '';
                const titleElem = document.querySelector('h1, [data-testid="article-headline"]');
                if (titleElem) title = titleElem.innerText.trim();
                
                if (!title && jsonData) {
                    try {
                        title = jsonData['props']['pageProps']['content']['headline'];
                    } catch(e) {}
                }
                if (!title && jsonData) {
                    try {
                        title = jsonData['props']['pageProps']['article']['headline'];
                    } catch(e) {}
                }
                
                let bodyText = '';
                const bodySelectors = [
                    'article',
                    '[data-component="article-body"]',
                    '.article-body',
                    '.body-content',
                    'main article',
                    '.content-body'
                ];
                for (const selector of bodySelectors) {
                    const elem = document.querySelector(selector);
                    if (elem) {
                        bodyText = elem.innerText.trim();
                        if (bodyText.length > 200) break;
                    }
                }
                
                if (bodyText.length < 200) {
                    const paragraphs = document.querySelectorAll('p');
                    bodyText = Array.from(paragraphs).map(p => p.innerText.trim()).join('\\n\\n');
                }
                
                return {
                    title: title,
                    body: bodyText,
                    json_data: jsonData
                };
            }
        ''')
        
        if not article_data['title']:
            parts = url.rstrip('/').split('/')
            article_data['title'] = parts[-1].replace('-', ' ').title()
        
        return article_data
    
    except PlaywrightTimeoutError:
        print(f"  超时: {url}")
        return {'title': '超时', 'body': ''}
    except Exception as e:
        print(f"  抓取失败: {str(e)}")
        return {'title': '抓取失败', 'body': ''}


def generate_epub(articles, date_str):
    """
    生成简单的 HTML 文件
    """
    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>The Economist - {date_str}</title>
    <style>
        body {{ font-family: 'Georgia', serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ text-align: center; border-bottom: 2px solid #ccc; padding-bottom: 10px; }}
        .article {{ margin: 20px 0; }}
        .article-title {{ font-size: 1.2em; font-weight: bold; }}
        .article-body {{ margin-top: 8px; line-height: 1.6; }}
        hr {{ border: 0; border-top: 1px solid #eee; }}
    </style>
</head>
<body>
    <h1>The Economist</h1>
    <p style="text-align:center;">{date_str}</p>
'''
    
    for i, article in enumerate(articles):
        if not article.get('title') or not article.get('body'):
            continue
        html_content += f'''
    <div class="article">
        <div class="article-title">{i+1}. {article['title']}</div>
        <div class="article-body">{article['body']}</div>
        <hr>
    </div>
'''
    
    html_content += '''
</body>
</html>'''
    
    output_file = f"economist_{date_str}.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"已生成 HTML 文件: {output_file}")
    return output_file


def main():
    print("=" * 60)
    print("The Economist 文章抓取工具 (Playwright)")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
        edition_url = f"https://www.economist.com/weeklyedition/{date_str}"
    else:
        edition_url = "https://www.economist.com/weeklyedition"
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    print(f"目标: {edition_url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            bypass_csp=True
        )
        page = context.new_page()
        page.set_default_timeout(30000)
        
        article_links = get_article_links(page, edition_url)
        if not article_links:
            print("未找到任何文章，请检查网站是否可访问")
            browser.close()
            sys.exit(1)
        
        articles = []
        total = len(article_links)
        for i, link in enumerate(article_links[:50]):
            print(f"进度: {i+1}/{min(total, 50)}")
            article_data = fetch_article_content(page, link['url'])
            if article_data['body'] and len(article_data['body']) > 100:
                articles.append({
                    'title': article_data['title'],
                    'body': article_data['body']
                })
                print(f"  ✓ 已抓取: {article_data['title'][:50]}...")
            else:
                print(f"  ✗ 正文太短或为空: {link['title']}")
            
            time.sleep(1 + (i % 3) * 0.5)
        
        browser.close()
    
    if articles:
        html_file = generate_epub(articles, date_str)
        print(f"\n成功抓取 {len(articles)} 篇文章")
        print(f"输出文件: {html_file}")
    else:
        print("未抓取到任何有效文章内容")


if __name__ == '__main__':
    main()
