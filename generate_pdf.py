import asyncio
import os
import json
import markdown
from playwright.async_api import async_playwright

async def main():
    with open("routing_research.md", "r") as f:
        md_content = f.read()
        
    # Convert Markdown to HTML in Python to preserve math blocks correctly
    # mdx_math extension prevents markdown from corrupting LaTeX underscores
    html_body = markdown.markdown(md_content, extensions=['mdx_math'])

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <script>
        window.MathJax = {{
          tex: {{
            inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
            displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
          }},
          startup: {{
            pageReady: () => {{
              return MathJax.startup.defaultPageReady().then(() => {{
                window.mathjax_done = true;
              }});
            }}
          }}
        }};
      </script>
      <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
      <style>
        body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 2em; }}
        h1, h2, h3 {{ color: #333; }}
        code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 4px; }}
        .MathJax_Display {{ overflow-x: auto; overflow-y: hidden; }}
      </style>
    </head>
    <body>
      <div id="content">{html_body}</div>
    </body>
    </html>
    """
    
    html_path = os.path.abspath("template.html")
    with open(html_path, "w") as f:
        f.write(html_content)
        
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        url = "file://" + html_path
        await page.goto(url)
        # Wait for MathJax to finish rendering
        await page.wait_for_function("window.mathjax_done === true", timeout=30000)
        await page.wait_for_timeout(1000) # extra wait for font loading
        await page.pdf(path="routing_research.pdf", format="A4", margin={"top":"1in", "right":"1in", "bottom":"1in", "left":"1in"})
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
